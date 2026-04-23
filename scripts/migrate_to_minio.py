from pathlib import Path

from obllomov.storage.assets.s3 import S3Assets
from obllomov.shared.path import HOLODECK_BASE_DATA_DIR
from obllomov.shared.env import env


assets = S3Assets(
    bucket_name=env.S3_BUCKET_NAME,
    key_prefix=env.S3_KEY_PREFIX,
    aws_access_key_id=env.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=env.AWS_SECRET_ACCESS_KEY,
    endpoint_url=env.S3_ENDPOINT_URL,
    region_name=env.AWS_DEFAULT_REGION,
    local_cache_dir="/tmp/s3_cache",
)

assets.upload_directory(
    local_dir=Path("~/.objathor-assets")/HOLODECK_BASE_DATA_DIR.expanduser(),
    relative_prefix=Path(),
)
