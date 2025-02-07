
import hydra
import os.path as osp
import tqdm

from hydra.utils import DictConfig
from sslh.datamodules.supervised import get_from_cfg
from sslh.transforms.get_from_name import get_transform


@hydra.main(config_path=osp.join('..', 'config'), config_name='supervised')
def main(cfg: DictConfig) -> None:
	train_transform = get_transform(cfg.data.acronym, 'identity', **cfg.data.transform)
	datamodule = get_from_cfg(cfg, train_transform, None, None)
	datamodule.prepare_data()
	datamodule.setup()

	train_dataloader = datamodule.train_dataloader()

	n_zeros_xs_total = 0
	n_zeros_ys_total = 0

	for batch in tqdm.tqdm(train_dataloader):
		xs, ys = batch
		n_zeros_xs = xs.eq(-100.0).all(dim=-1).all(dim=-1).squeeze()
		n_zeros_ys = ys.eq(0.0).all(dim=-1).squeeze()

		assert list(n_zeros_xs.shape) == [cfg.bsize], f'{list(n_zeros_xs.shape)} != {[cfg.bsize]}'
		assert list(n_zeros_ys.shape) == [cfg.bsize], f'{list(n_zeros_ys.shape)} != {[cfg.bsize]}'
		n_zeros_xs_total += n_zeros_xs.sum().item()
		n_zeros_ys_total += n_zeros_ys.sum().item()

	n_samples_total = len(train_dataloader) * cfg.bsize
	print('xs zero samples = ', n_zeros_xs_total)
	print('ys zero samples = ', n_zeros_ys_total)
	print('Total samples = ', n_samples_total)


if __name__ == '__main__':
	main()
