query ?= A lightful living room, small bedroom and tiny kitchen
save_dir ?= ./scenes
scene_path = ./scenes/A_lightful_living_room,_small/A_lightful_living_room,_small.json
mock ?= 0

run: 
	uvicorn obllomov.main:app --reload
	
req:
	pipreqs --mode gt --force . 

generate:
	export PYTHONPATH="." && python scripts/generate.py --query "$(query)" --save-dir "$(save_dir)" \
	$(if $(filter 1,$(mock)),--mock)

rendering:
	export PYTHONPATH="." && python -u render/render.py "$(scene_path)" 

minio:
	docker run -d \
	--name minio \
	-p 9000:9000 \
	-p 9001:9001 \
	-e MINIO_ROOT_USER=minioadmin \
	-e MINIO_ROOT_PASSWORD=minioadmin \
	-v ~/minio-data:/data \
	quay.io/minio/minio server /data --console-address ":9001"




