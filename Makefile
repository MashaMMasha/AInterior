query ?= A lightful living room, small bedroom and tiny kitchen
save_dir ?= ./scenes
session_id ?=
mock ?= 0

run:
	export PYTHONPATH="./agents-service" && uvicorn main:app --reload --app-dir agents-service --port 8006
	
req:
	pipreqs --mode gt --force . 

generate:
	export PYTHONPATH="./agents-service" && python scripts/generate.py \
	--query "$(query)" --save-dir "$(save_dir)" \
	$(if $(filter 1,$(mock)),--mock) \
	$(if $(session_id),--session-id "$(session_id)")

setup-assets:
	@echo "Downloading and setting up assets... This might take 20-40 minutes."
	mkdir -p ~/.objathor-assets/2023_09_23
	curl -L -C - -o ~/.objathor-assets/2023_09_23/assets.tar "https://pub-daedd7738a984186a00f2ab264d06a07.r2.dev/2023_09_23/assets.tar"
	@echo "Extracting assets..."
	cd ~/.objathor-assets/2023_09_23 && tar -xf assets.tar
	@echo "Linking holodeck/2023_09_23 -> 2023_09_23 (path expected by ObLLoMov)..."
	@mkdir -p ~/.objathor-assets/holodeck
	@ln -sfn "$$HOME/.objathor-assets/2023_09_23" "$$HOME/.objathor-assets/holodeck/2023_09_23"
	@echo "Uploading to MinIO bucket ainterior-assets (same as agents-service in docker-compose)..."
	@echo "Заливка в MinIO: поднимите stack (minio) и выполните: make upload-assets-docker"
	@echo "Done!"

# Остановить Colima и поднять с большим RAM/диском (удобно для MinIO + assets + ML).
# Диск уменьшить нельзя: если уже 100GiB+, параметр --disk будет проигнорирован или поднимут до 120GiB.
colima-big:
	colima stop || true
	colima start --memory 16 --cpu 8 --disk 120

rendering:
	export PYTHONPATH="./agents-service" && python -u scripts/render/render.py "$(session_id)"

render-stream:
	export PYTHONPATH="./agents-service" && python -u scripts/render/render_stream.py "$(generation_id)"

minio:
	docker run -d \
	--name minio \
	-p 9000:9000 \
	-p 9001:9001 \
	-e MINIO_ROOT_USER=minioadmin \
	-e MINIO_ROOT_PASSWORD=minioadmin \
	-v ~/minio-data:/data \
	quay.io/minio/minio server /data --console-address ":9001"

docker-up:
	export DOCKER_HOST="unix:/$$HOME/.colima/default/docker.sock" && docker compose up -d

docker-build:
	export DOCKER_HOST="unix:/$$HOME/.colima/default/docker.sock" && docker compose up -d --build

docker-logs:
	export DOCKER_HOST="unix:/$$HOME/.colima/default/docker.sock" && docker compose logs -f

# `docker compose logs` — имя сервиса из docker-compose (например agents-service), не container_name (ainterior-agents-service).
docker-logs-agents:
	docker compose logs -f --tail=200 agents-service

# Требуется: docker compose up -d (minio + minio-init), локальный каталог ~/.objathor-assets (make setup-assets).
# Путь: OBJATHOR_ASSETS_DIR=... make upload-assets-docker
upload-assets-docker:
	docker compose --profile upload run --rm upload-objathor-assets

frontend-dev:
	cd frontend && npm run dev
