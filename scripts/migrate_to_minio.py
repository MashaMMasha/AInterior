import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents-service"))

# Load .env manually
from dotenv import load_dotenv
load_dotenv()

from obllomov.storage.assets.s3 import S3Assets

print("Starting migration to MinIO...")

# Use environment variables directly
s3_endpoint = os.getenv('S3_ENDPOINT', 'http://localhost:9000')
s3_bucket = os.getenv('S3_BUCKET', 'ainterior-assets') 
aws_access_key = os.getenv('S3_ACCESS_KEY', 'minioadmin')
aws_secret_key = os.getenv('S3_SECRET_KEY', 'minioadmin')
aws_region = os.getenv('S3_REGION', 'us-east-1')

print(f"S3_ENDPOINT: {s3_endpoint}")
print(f"S3_BUCKET: {s3_bucket}")

assets = S3Assets(
    bucket_name=s3_bucket,
    key_prefix="",
    aws_access_key_id=aws_access_key,
    aws_secret_access_key=aws_secret_key,
    endpoint_url=s3_endpoint,
    region_name=aws_region,
    local_cache_dir="/tmp/s3_cache",
)

# Use the correct path - just 2023_09_23
local_path = Path("~/.objathor-assets/2023_09_23").expanduser()
print(f"Uploading from: {local_path}")

if not local_path.exists():
    print(f"Error: Local directory {local_path} does not exist.")
    print("Available directories:")
    assets_base = Path("~/.objathor-assets").expanduser()
    if assets_base.exists():
        for item in assets_base.iterdir():
            print(f"  {item}")
    sys.exit(1)

assets.upload_directory(
    local_dir=local_path,
    relative_prefix=Path(),
)

print("Successfully migrated assets to MinIO!")