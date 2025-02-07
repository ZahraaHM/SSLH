"""
	ESC-50 core classes and functions.
	Developed by Léo Cances (leocances on Github).

	Modified : Yes
		- typing & imports
"""

import numpy
import os
import torchaudio

from torch import Tensor
from torch.nn import Module
from torch.utils.data.dataset import Dataset
from torchaudio.datasets.utils import download_url, extract_archive
from typing import Tuple

# Download URL and checksums
URL = {
	'esc10-10': 'https://github.com/karoldvl/ESC-50/archive/master.zip',
	'esc10-50': 'https://github.com/karoldvl/ESC-50/archive/master.zip',
	# 'esc10-us': None,
}

_CHECKSUMS = {
	'esc10-10': None,
	'esc10-50': None,
	# 'esc10-us': None,
}

# Constant
ARCHIVE_BASENAME = 'ESC-50-master'
FOLDER_IN_ARCHIVE = 'ESC-50-master'
AUDIO_FOLDER = 'audio'
META_FOLDER = 'meta'
AVAILABLE_VERSION = list(URL.keys())

# Default parameters
FOLDS = (1, 2, 3, 4, 5)


def cache_feature(func):
	def decorator(*args, **kwargs):
		key = ','.join(map(str, args))

		if key not in decorator.cache:
			decorator.cache[key] = func(*args, **kwargs)

		return decorator.cache[key]

	decorator.cache = dict()
	return decorator


class ESC50Base(Dataset):
	"""
	ESC wrappers

	Args:
		root (string): Root directory of wrappers where directory
			``ESC-50-master`` exists or will be saved to if download is set to True.
		download (bool, optional): If true, download the dataset from the internet
			and puts it in root directory. If wrappers is already downloaded, it is
			not downloaded again.
	"""
	NB_CLASS = 50

	def __init__(
		self,
		root: str,
		folds: tuple = FOLDS,
		download: bool = False,
		transform: Module = None
	) -> None:
		super().__init__()

		self.root = root
		self.required_folds = folds
		self.transform = transform

		self.url = URL['esc10-50']
		self.n_class = 50
		self.target_directory = os.path.join(self.root, FOLDER_IN_ARCHIVE)

		# Dataset must exist to continue
		if download:
			self.download()
		# elif not self.check_integrity(self.target_directory):
		#     raise RuntimeError('Dataset not found or corrupted. \n\
		#         You can use download=True to download it.')

		# Prepare the medata
		self._filenames = []
		self._folds = []
		self._targets = []
		self._esc10s = []
		self._load_metadata()

	def __getitem__(self, index: int) -> Tuple[Tensor, int, int]:
		"""
		Args:
			index (int): Index

		Returns:
			tuple: (raw_audio, sr, target).
		"""
		data, sampling_rate, target = self.load_item(index)

		if self.transform is not None:
			data = self.transform(data)

		return data, sampling_rate, target

	def __len__(self) -> int:
		return len(self._filenames)

	def _load_metadata(self) -> None:
		"""Read the metadata csv file and gather the information needed."""
		# HEADER COLUMN NUMBER
		c_filename = 0
		c_fold = 1
		c_target = 2
		c_esc10 = 4

		self._filenames = []
		self._folds = []
		self._targets = []
		self._esc10s = []

		# Read the csv file and remove header
		path = os.path.join(self.target_directory, META_FOLDER, 'esc50.csv')
		with open(path, 'r') as fp:
			data = fp.read().splitlines()[1:]

			for line in data:
				items = line.split(',')

				self._filenames.append(items[c_filename])
				self._folds.append(int(items[c_fold]))
				self._targets.append(int(items[c_target]))
				self._esc10s.append(eval(items[c_esc10]))

		self._filenames = numpy.asarray(self._filenames)
		self._folds = numpy.asarray(self._folds)
		self._targets = numpy.asarray(self._targets)
		self._esc10s = numpy.asarray(self._esc10s)

		# Keep only the required folds
		folds_mask = sum([self._folds == f for f in self.required_folds]) >= 1

		self._filenames = self._filenames[folds_mask]
		self._targets = self._targets[folds_mask]
		self._esc10s = self._esc10s[folds_mask]

	def download(self) -> None:
		"""Download the dataset and extract the archive"""
		if self.check_integrity(self.target_directory):
			print('Dataset already downloaded and verified.')

		else:
			if not os.path.isdir(self.root):
				os.makedirs(self.root)
			
			archive_path = os.path.join(self.root, FOLDER_IN_ARCHIVE + '.zip')
			download_url(self.url, self.root)
			extract_archive(archive_path, self.root)

	def check_integrity(self, path, checksum=None) -> bool:
		"""Check if the dataset already exist and if yes, if it is not corrupted.

		Returns:
			bool: False if the dataset doesn't exist or if it is corrupted.
		"""
		if not os.path.isdir(path):
			return False

		# add checksum verification
		return True

	def load_item(self, index: int) -> Tuple[Tensor, int, int]:
		filename = self._filenames[index]
		target = self._targets[index]

		path = os.path.join(self.target_directory, AUDIO_FOLDER, filename)
		waveform, sample_rate = torchaudio.load(path)

		return waveform, sample_rate, target


class ESC50(ESC50Base):
	@cache_feature
	def __getitem__(self, index: int) -> Tuple[Tensor, int]:
		x, sr, y = super().__getitem__(index)
		return x, y
