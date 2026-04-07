import os
import tempfile
import threading
from pathlib import Path
from typing import Iterator, Optional

import boto3
from botocore.exceptions import ClientError

from obllomov.shared.env import env
from obllomov.shared.log import logger

from .base import BaseAssets


class S3Assets(BaseAssets):
    def __init__(
        self,
        bucket_name: Optional[str] = None,       
        key_prefix: Optional[str] = None,         
        aws_access_key_id: Optional[str] = None,  
        aws_secret_access_key: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        region_name: Optional[str] = None,
        local_cache_dir: Optional[str] = None,
    ) -> None:
        self.bucket_name = bucket_name or env.S3_BUCKET_NAME
        key_prefix = key_prefix if key_prefix is not None else env.S3_KEY_PREFIX
        self.key_prefix = key_prefix.rstrip("/")

        if local_cache_dir is None:
            local_cache_dir = os.path.join(tempfile.gettempdir(), "s3_assets_cache")
        self.cache_dir = Path(local_cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._cache_lock = threading.Lock()
        self._cached_paths: dict[str, Path] = {}

        session = boto3.session.Session()
        self._s3 = session.client(
            service_name="s3",
            aws_access_key_id=aws_access_key_id or env.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=aws_secret_access_key or env.AWS_SECRET_ACCESS_KEY,
            endpoint_url=endpoint_url or env.S3_ENDPOINT_URL,
            region_name=region_name or env.AWS_DEFAULT_REGION,
        )


    def _s3_key(self, relative_path: Path | str) -> str:
        rel = str(self._to_path(relative_path))
        if self.key_prefix:
            return f"{self.key_prefix}/{rel}"
        return rel

    def _cache_path(self, relative_path: Path | str) -> Path:
        return self.cache_dir / self._to_path(relative_path)

    def _ensure_cached(self, relative_path: Path | str) -> Path:
        path = self._to_path(relative_path)
        key = str(path)

        with self._cache_lock:
            cached = self._cached_paths.get(key)
            if cached is not None and cached.is_file():
                return cached

        local_path = self._cache_path(path)
        local_path.parent.mkdir(parents=True, exist_ok=True)

        self._s3.download_file(
            Bucket=self.bucket_name,
            Key=self._s3_key(path),
            Filename=str(local_path),
        )

        with self._cache_lock:
            self._cached_paths[key] = local_path

        return local_path

    def _invalidate_cache(self, relative_path: Path | str) -> None:
        key = str(relative_path)
        with self._cache_lock:
            self._cached_paths.pop(key, None)

    def exists(self, relative_path: Path | str) -> bool:
        try:
            self._s3.head_object(
                Bucket=self.bucket_name,
                Key=self._s3_key(relative_path),
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
                return False
            raise

    def read_bytes(self, relative_path: Path | str) -> bytes:
        response = self._s3.get_object(
            Bucket=self.bucket_name,
            Key=self._s3_key(relative_path),
        )
        logger.debug("read bytes")
        return response["Body"].read()

    def read_bytes_or_none(self, relative_path: Path | str) -> Optional[bytes]:
        try:
            response = self._s3.get_object(
                Bucket=self.bucket_name,
                Key=self._s3_key(relative_path),
            )
            return response["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
                return None
            raise

    def write_bytes(self, relative_path: Path | str, data: bytes) -> None:
        self._s3.put_object(
            Bucket=self.bucket_name,
            Key=self._s3_key(relative_path),
            Body=data,
        )
        self._invalidate_cache(relative_path)

    def list_files(self, relative_prefix: Path | str = Path()) -> Iterator[Path]:
        rel_str = str(relative_prefix)
        prefix = self._s3_key(rel_str) if rel_str and rel_str != "." else self.key_prefix
        if prefix and not prefix.endswith("/"):
            prefix += "/"

        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
            for obj in page.get("Contents", []):
                key: str = obj["Key"]
                if self.key_prefix and key.startswith(self.key_prefix + "/"):
                    yield Path(key[len(self.key_prefix) + 1:])
                else:
                    yield Path(key)

    def delete(self, relative_path: Path | str) -> None:
        self._s3.delete_object(
            Bucket=self.bucket_name,
            Key=self._s3_key(relative_path),
        )
        self._invalidate_cache(relative_path)

    def get_local_path(self, relative_path: Path | str) -> Path:
        return self._ensure_cached(relative_path)

    def get_local_dir(self, relative_prefix: Path | str) -> Path:
        rel = self._to_path(relative_prefix)
        local_root = self.cache_dir
        self.download_directory(rel, local_root, skip_existing=True)
        return local_root / rel

    def upload_directory(
        self,
        local_dir: Path | str,
        relative_prefix: Path | str = Path(),
    ) -> None:
        local_root = Path(local_dir).expanduser().resolve()
        rel_prefix = self._to_path(relative_prefix)

        files = [f for f in local_root.rglob("*") if f.is_file()]
        total = len(files)

        for uploaded, local_path in enumerate(files, start=1):
            rel = local_path.relative_to(local_root)
            s3_relative = rel_prefix / rel if str(rel_prefix) != "." else rel
            self.upload_from_local(local_path, s3_relative)

            if uploaded % 100 == 0 or uploaded == total:
                print(f"  Загружено {uploaded}/{total}: {s3_relative}")

    def download_directory(
        self,
        relative_prefix: Path | str,
        local_dir: Path | str,
        skip_existing: bool = True,
    ) -> None:
        local_root = Path(local_dir)
        for relative_path in self.list_files(relative_prefix):
            local_path = local_root / relative_path
            if skip_existing and local_path.is_file():
                continue
            self.download_to_local(relative_path, local_path)

    def invalidate_cache(self, relative_path: Optional[Path | str] = None) -> None:
        with self._cache_lock:
            if relative_path is None:
                self._cached_paths.clear()
            else:
                key = str(self._to_path(relative_path))
                self._cached_paths.pop(key, None)
