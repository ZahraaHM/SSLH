"""
	Main script for running a Supervised training.
	WARNING : It use only 10% of the dataset by default (use "--supervised_ratio 1.0" argument for running on 100% of the dataset).
"""

import torch

from argparse import ArgumentParser, Namespace

from mlu.utils.misc import get_datetime, reset_seed

from ssl.datasets.get_interface import get_dataset_interface, DatasetInterface
from ssl.supervised.trainer import SupervisedTrainer
from ssl.utils.args import post_process_args, check_args, add_common_args
from ssl.utils.cross_validation import cross_validation
from ssl.utils.misc import (
	build_optimizer, build_scheduler, build_tensorboard_writer, build_checkpoint, get_prefix
)
from ssl.utils.other_metrics import CategoricalAccuracyOnehot, CrossEntropyMetric, EntropyMetric, MaxMetric
from ssl.utils.recorder.recorder import Recorder
from ssl.utils.save import save_results
from mlu.nn import CrossEntropyWithVectors
from ssl.utils.types import str_to_optional_str
from ssl.validation.validater import Validater

from time import time
from torch.utils.data import DataLoader, Subset
from typing import Optional, Dict, Union


TRAIN_NAME = "Supervised"


def create_args() -> Namespace:
	parser = ArgumentParser()
	add_common_args(parser)

	group_su = parser.add_argument_group(TRAIN_NAME)
	group_su.add_argument("--augm_none", type=str_to_optional_str, default=None,
		help="Augment pool for default training dataset. (default: None)")

	args = parser.parse_args()
	args = post_process_args(args)
	check_args(args)

	return args


def run_supervised(args: Namespace, start_date: str, fold_val: Optional[int], interface: DatasetInterface) -> Dict[str, Union[float, int]]:
	# Build loaders
	if interface.get_nb_folds() is None:
		folds_train, folds_val = None, None
	else:
		if fold_val is None:
			fold_val = interface.get_nb_folds()
		folds_train = list(range(1, interface.get_nb_folds() + 1))
		folds_train.remove(fold_val)
		folds_val = [fold_val]

	dataset_train = interface.get_dataset_train(args, folds_train)
	dataset_val = interface.get_dataset_val(args, folds_val)
	dataset_eval = interface.get_dataset_eval(args, None)

	if args.supervised_ratio < 1.0:
		indexes = interface.generate_indexes_for_split(dataset_train, [args.supervised_ratio])[0]
		dataset_train = Subset(dataset_train, indexes)

	loader_train = DataLoader(dataset_train, batch_size=args.batch_size_s, shuffle=True, num_workers=8, drop_last=True)
	loader_val = DataLoader(dataset_val, batch_size=args.batch_size_s, shuffle=False, drop_last=False)

	# Prepare model
	model = interface.build_model(args.model, args)
	model_name = model.__class__.__name__
	optim = build_optimizer(args, model)
	activation = lambda x, dim: x.softmax(dim=dim).clamp(min=2e-30)

	criterion = CrossEntropyWithVectors()

	sched = build_scheduler(args, optim)

	# Prepare metrics
	main_metric_name = "val/acc"
	metrics_train = {"acc": CategoricalAccuracyOnehot(dim=1)}
	metrics_val = {
		"acc": CategoricalAccuracyOnehot(dim=1),
		"ce": CrossEntropyMetric(dim=1),
		"entropy": EntropyMetric(dim=1),
		"max": MaxMetric(dim=1),
	}

	# Prepare objects for saving data
	prefix = get_prefix(args, folds_val, interface, start_date, model_name, TRAIN_NAME)
	writer, dirpath_writer = build_tensorboard_writer(args, prefix)
	recorder = Recorder(writer)
	checkpoint = build_checkpoint(args, dirpath_writer, model, optim)

	# Start main training
	trainer = SupervisedTrainer(model, activation, optim, loader_train, metrics_train, recorder, criterion)
	validator = Validater(model, activation, loader_val, metrics_val, recorder, checkpoint=checkpoint, checkpoint_metric=main_metric_name)

	if sched is not None:
		validator.add_callback_on_end(sched)

	print("Dataset : {:s} (train={:d}, val={:d}, eval={:s}).".format(
		args.dataset_name,
		len(dataset_train),
		len(dataset_val),
		str(len(dataset_eval)) if dataset_eval is not None else "None"
	))
	print("\nStart {:s} training on {:s} with model \"{:s}\" and {:d} epochs ({:s})...".format(TRAIN_NAME, args.dataset_name, model_name, args.nb_epochs, args.tag))
	start_time = time()

	for epoch in range(args.nb_epochs):
		trainer.train(epoch)
		validator.val(epoch)

	print("\nEnd {:s} training. (duration = {:.2f})".format(TRAIN_NAME, time() - start_time))

	if dataset_eval is not None and checkpoint is not None and checkpoint.is_saved():
		recorder.deactivate_auto_storage()
		checkpoint.load_best_state(model, None)
		loader_eval = DataLoader(dataset_eval, batch_size=args.batch_size_s, shuffle=False, drop_last=False)
		validator = Validater(model, activation, loader_eval, metrics_val, recorder, name="eval")
		validator.val(0)

	# Save results
	save_results(dirpath_writer, args, recorder, interface.get_transforms(args), main_metric_name, start_date, folds_val)

	if not recorder.is_empty():
		best = recorder.get_best_epoch(main_metric_name)
		print("Metric : \"{:s}\"".format(main_metric_name))
		print("Best epoch : {:d}".format(best["best_epoch"]))
		print("Best mean : {:f}".format(best["best_mean"]))
		print("Best std : {:f}".format(best["best_std"]))
	else:
		best = {}

	return best


def main():
	# Initialisation
	start_time = time()
	start_date = get_datetime()

	args = create_args()
	args.start_date = start_date
	args.train_name = TRAIN_NAME

	reset_seed(args.seed)
	torch.autograd.set_detect_anomaly(args.debug_mode)
	torch.cuda.empty_cache()

	print("Start {:s}. (tag: \"{:s}\")".format(TRAIN_NAME, args.tag))
	print(" - start_date: {:s}".format(start_date))

	# Prepare dataloaders
	interface = get_dataset_interface(args.dataset_name)
	args.nb_classes = interface.get_nb_classes()

	# Run
	if args.cross_validation:
		cross_validation(run_supervised, args, start_date, interface, TRAIN_NAME)
	else:
		run_supervised(args, start_date, args.fold_val, interface)

	exec_time = time() - start_time
	print("")
	print("Program started at \"{:s}\" and terminated at \"{:s}\".".format(start_date, get_datetime()))
	print("Total execution time: {:.2f}s".format(exec_time))


if __name__ == "__main__":
	main()
