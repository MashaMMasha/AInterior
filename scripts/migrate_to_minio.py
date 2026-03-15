from pathlib import Path

from obllomov.storage.assets.s3 import S3Assets

assets = S3Assets(
    bucket_name="ainterior-assets",
    key_prefix="objathor-assets",
    aws_access_key_id="minioadmin",
    aws_secret_access_key="minioadmin",
    endpoint_url="http://localhost:9000",
    region_name="us-east-1",
    local_cache_dir="/tmp/s3_cache",
)

assets.upload_directory(
    local_dir=Path("~/.objathor-assets").expanduser(),
    relative_prefix=Path(),
)
