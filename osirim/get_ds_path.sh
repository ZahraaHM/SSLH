
dataset_path="UNKNOWN_DATASET_PATH"

case $1 in
	"CIFAR10" )
		dataset_path="/projets/samova/leocances/CIFAR10/";;
	"UBS8K" )
		dataset_path="/projets/samova/leocances/UrbanSound8K/";;
	"ESC10" )
		dataset_path="/projets/samova/elabbe/ESC10/";;
	"ESC50" )
		dataset_path="/projets/samova/elabbe/ESC50/";;
	"GSC" )
		dataset_path="/projets/samova/elabbe/GSC/";;
	"GSC12" )
		dataset_path="/projets/samova/elabbe/GSC/";;
	"AUDIOSET" )
		dataset_path="/projets/samova/leocances/AudioSet/hdfs/";;
	"AUDIOSET_RAW" )
		dataset_path="/projets/samova/CORPORA/AUDIOSET/";;
esac

echo "$dataset_path"
