
from setuptools import setup, find_packages
from setuptools.command.develop import develop
from setuptools.command.install import install
from subprocess import check_call


install_requires = [
	"torch~=1.7.1",
	"torchaudio~=0.7.2",
	"torchvision~=0.8.2",
	"pytorch-lightning~=1.2.3",
	"hydra-core~=1.0.6",
	"tensorboard",
	"matplotlib",
	"numpy",
	"librosa",
	"h5py",
	"pandas",
	"tqdm",
	"soundfile",
	"advertorch",
	"ubs8k @ git+https://github.com/leocances/UrbanSound8K@8cd9b1071c137e94f7f4cc7b1a60ac9265988a52",
	"MLU @ git+https://github.com/Labbeti/MLU@v0.4.6",
]


class PostDevelopCommand(develop):
	def run(self):
		super().run()
		check_call(["bash", "build_directories.sh"])


class PostInstallCommand(install):
	def run(self):
		super().run()
		check_call(["bash", "build_directories.sh"])


setup(
	name="sslh",
	version="2.1.0",
	packages=find_packages(),
	url="https://github.com/Labbeti/SSLH",
	license="",
	author="Etienne Labbé",
	author_email="etienne.labbe31@gmail.com",
	description="Semi Supervised Learning with Holistic methods.",
	python_requires=">=3.8.5",
	install_requires=install_requires,
	include_package_data=True,
	cmdclass={
		"develop": PostDevelopCommand,
		"install": PostInstallCommand,
	}
)
