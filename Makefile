query ?= "A lightful living room, small bedroom and tiny kitchen"
save_dir ?= "./scenes"

run: 
	uvicorn obllomov.main:app --reload
	
req:
	pipreqs --mode gt --force . 

generate:
	python generate.py --query $(query) --save-dir $(save_dir)

minio:
	docker run -d \
	--name minio \
	-p 9000:9000 \
	-p 9001:9001 \
	-e MINIO_ROOT_USER=minioadmin \
	-e MINIO_ROOT_PASSWORD=minioadmin \
	-v ~/minio-data:/data \
	quay.io/minio/minio server /data --console-address ":9001"


