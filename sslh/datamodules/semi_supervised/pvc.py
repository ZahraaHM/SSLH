
from pytorch_lightning import LightningDataModule
from torch.utils.data.dataloader import DataLoader
from typing import Callable, Optional, Tuple

from mlu.datasets.samplers import SubsetCycleSampler
from mlu.datasets.wrappers import TransformDataset, NoLabelDataset
from sslh.datasets.pvc import ComParE2021PRS, IterationBalancedSampler, class_balance_split


N_CLASSES = 5


class PVCDataModuleSSL(LightningDataModule):
	def __init__(
		self,
		root: str,
		transform_train_s: Optional[Callable] = None,
		transform_train_u: Optional[Callable] = None,
		transform_val: Optional[Callable] = None,
		target_transform: Optional[Callable] = None,
		bsize_train_s: int = 64,
		bsize_train_u: int = 64,
		n_workers_s: int = 2,
		n_workers_u: int = 3,
		drop_last: bool = True,
		pin_memory: bool = False,
		ratio_s: float = 0.1,
		ratio_u: float = 0.9,
		duplicate_loader_s: bool = False,
		n_train_steps_u: Optional[int] = 50000,
	):
		"""
			LightningDataModule of Primate Vocalization Corpus (PVC) for semi-supervised trainings.

			Note: The splits of the dataset has the same class distribution.

			:param root: The root path of the dataset.
			:param transform_train_s: The optional transform to apply to supervised train data. (default: None)
			:param transform_train_u: The optional transform to apply to unsupervised train data. (default: None)
			:param transform_val: The optional transform to apply to validation data. (default: None)
			:param target_transform: The optional transform to apply to train and validation targets. (default: None)
			:param bsize_train_s: The batch size used for supervised train data. (default: 64)
			:param bsize_train_u: The batch size used for unsupervised train data. (default: 64)
			:param n_workers_s: The number of workers for supervised train dataloader. (default: 2)
			:param n_workers_s: The number of workers for unsupervised train dataloader. (default: 3)
			:param drop_last: If True, drop the last incomplete batch. (default: False)
			:param pin_memory: If True, pin the memory of dataloader. (default: False)
			:param ratio_s: The ratio of the supervised subset len in [0, 1]. (default: 0.1)
			:param ratio_u: The ratio of the unsupervised subset len in [0, 1]. (default: 0.9)
			:param duplicate_loader_s: If True, duplicate the supervised dataloader for DCT training. (default: False)
			:param n_train_steps_u: The number of train steps for PVC.
				If None, the number will be set to the number of train labeled data.
				(default: 50000)
		"""
		super().__init__()
		self.root = root
		self.transform_train_s = transform_train_s
		self.transform_train_u = transform_train_u
		self.transform_val = transform_val
		self.transform_test = transform_val
		self.target_transform = target_transform
		self.bsize_train_s = bsize_train_s
		self.bsize_train_u = bsize_train_u
		self.bsize_val = bsize_train_s + bsize_train_u
		self.bsize_test = bsize_train_s + bsize_train_u
		self.n_workers_s = n_workers_s
		self.n_workers_u = n_workers_u
		self.drop_last = drop_last
		self.pin_memory = pin_memory
		self.ratio_s = ratio_s
		self.ratio_u = ratio_u
		self.duplicate_loader_s = duplicate_loader_s

		self.n_train_steps_u = n_train_steps_u

		self.train_dataset_raw = None
		self.val_dataset_raw = None
		self.test_dataset_raw = None

		self.sampler_s = None
		self.sampler_u = None
		self.example_input_array = None

	def prepare_data(self, *args, **kwargs):
		pass

	def setup(self, stage: Optional[str] = None):
		if stage == 'fit':
			self.train_dataset_raw = ComParE2021PRS(self.root, 'train', transform=None)
			self.val_dataset_raw = ComParE2021PRS(self.root, 'devel', transform=None)

			indexes_s, indexes_u = class_balance_split(self.train_dataset_raw, self.ratio_s, self.ratio_u)

			if self.n_train_steps_u is None:
				n_train_samples_s = len(indexes_s) * self.bsize_train_s
				n_train_samples_u = len(indexes_u) * self.bsize_train_u
			else:
				n_train_samples_s = self.n_train_steps_u * self.bsize_train_s
				n_train_samples_u = self.n_train_steps_u * self.bsize_train_u

			self.sampler_s = IterationBalancedSampler(self.train_dataset_raw, indexes_s, n_train_samples_s)
			self.sampler_u = SubsetCycleSampler(indexes_u, n_train_samples_u)

			dataloader = self.val_dataloader()
			xs, ys = next(iter(dataloader))
			self.example_input_array = xs
			self.dims = tuple(xs.shape)

		elif stage == 'test':
			# The 'test' subset is unlabeled, so we do not use it for now
			self.test_dataset_raw = None

	def train_dataloader(self) -> Tuple[DataLoader, ...]:
		train_dataset_s = TransformDataset(self.train_dataset_raw, self.transform_train_s, index=0)
		train_dataset_s = TransformDataset(train_dataset_s, self.target_transform, index=1)

		train_dataset_u = TransformDataset(self.train_dataset_raw, self.transform_train_u, index=0)
		train_dataset_u = NoLabelDataset(train_dataset_u)

		loader_s = DataLoader(
			dataset=train_dataset_s,
			batch_size=self.bsize_train_s,
			num_workers=self.n_workers_s,
			sampler=self.sampler_s,
			drop_last=self.drop_last,
			pin_memory=self.pin_memory,
		)
		loader_u = DataLoader(
			dataset=train_dataset_u,
			batch_size=self.bsize_train_u,
			num_workers=self.n_workers_u,
			sampler=self.sampler_u,
			drop_last=self.drop_last,
			pin_memory=self.pin_memory,
		)

		if not self.duplicate_loader_s:
			loaders = loader_s, loader_u
		else:
			loaders = loader_s, loader_s, loader_u

		return loaders

	def val_dataloader(self) -> Optional[DataLoader]:
		val_dataset = self.val_dataset_raw
		if val_dataset is None:
			return None

		val_dataset = TransformDataset(val_dataset, self.transform_val, index=0)
		val_dataset = TransformDataset(val_dataset, self.target_transform, index=1)

		loader = DataLoader(
			dataset=val_dataset,
			batch_size=self.bsize_val,
			num_workers=self.n_workers_s + self.n_workers_u,
			drop_last=False,
		)
		return loader

	def test_dataloader(self) -> Optional[DataLoader]:
		test_dataset = self.test_dataset_raw
		if test_dataset is None:
			return None

		test_dataset = TransformDataset(test_dataset, self.transform_test, index=0)
		test_dataset = TransformDataset(test_dataset, self.target_transform, index=1)

		loader = DataLoader(
			dataset=test_dataset,
			batch_size=self.bsize_test,
			num_workers=self.n_workers_s + self.n_workers_u,
			drop_last=False,
		)
		return loader
