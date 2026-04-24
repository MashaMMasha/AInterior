import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents-service"))

from obllomov.shared.env import env
from obllomov.storage.assets.s3 import S3Assets

def main():
    if not env.S3_BUCKET_NAME or not env.S3_ENDPOINT_URL:
        print("Error: S3_BUCKET_NAME and S3_ENDPOINT_URL must be set in .env")
        sys.exit(1)

    print(f"Uploading assets to S3 ({env.S3_ENDPOINT_URL}) bucket {env.S3_BUCKET_NAME}...")

    assets = S3Assets()
    
    local_dir = Path(env.OBJATHOR_ASSETS_BASE_DIR).expanduser()
    if not local_dir.exists():
        print(f"Error: Local directory {local_dir} does not exist.")
        print("Please run `make setup-assets` to download them.")
        sys.exit(1)

    assets.upload_directory(
        local_dir=local_dir,
        relative_prefix=Path(),
    )
    print("Successfully uploaded all assets to S3.")

if __name__ == "__main__":
    main()