import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from pathlib import Path
from typing import Optional, BinaryIO
import logging
import os
from ml_service.config import settings as ml_settings

logger = logging.getLogger(__name__)


class S3Service:
    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        bucket_name: Optional[str] = None,
        region: str = "us-east-1"
    ):
        self.endpoint_url = endpoint_url or os.getenv("S3_ENDPOINT", "http://localhost:9000")
        self.access_key = access_key or os.getenv("S3_ACCESS_KEY", "minioadmin")
        self.secret_key = secret_key or os.getenv("S3_SECRET_KEY", "minioadmin")
        self.bucket_name = bucket_name or os.getenv("S3_BUCKET", "ainterior-models")
        self.region = region

        self.client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            config=Config(signature_version='s3v4')
        )

        self._available = False
        try:
            self._ensure_bucket_exists()
            self._available = True
        except Exception as e:
            logger.warning(f"S3 недоступен ({self.endpoint_url}): {e}")

    def _ensure_bucket_exists(self):
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                self.client.create_bucket(Bucket=self.bucket_name)
            else:
                raise

    def upload_file(
        self,
        file_path: str,
        object_name: Optional[str] = None,
        metadata: Optional[dict] = None,
        content_type: Optional[str] = None
    ) -> str:
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Файл не найден: {file_path}")

        if object_name is None:
            object_name = file_path.name

        if content_type is None:
            content_type = self._get_content_type(file_path)

        extra_args = {'ContentType': content_type}
        if metadata:
            extra_args['Metadata'] = metadata

        try:
            self.client.upload_file(str(file_path), self.bucket_name, object_name, ExtraArgs=extra_args)
            return object_name
        except ClientError as e:
            logger.error(f"Ошибка загрузки файла: {e}")
            raise
    
    def upload_fileobj(self, file_obj: BinaryIO, object_name: str, metadata: Optional[dict] = None, content_type: str = "application/octet-stream") -> str:
        extra_args = {'ContentType': content_type}
        if metadata:
            extra_args['Metadata'] = metadata

        try:
            self.client.upload_fileobj(file_obj, self.bucket_name, object_name, ExtraArgs=extra_args)
            return object_name
        except ClientError as e:
            logger.error(f"Ошибка загрузки объекта: {e}")
            raise

    def download_file(self, object_name: str, local_path: str) -> str:
        try:
            self.client.download_file(self.bucket_name, object_name, local_path)
            return local_path
        except ClientError as e:
            logger.error(f"Ошибка скачивания файла: {e}")
            raise

    def get_presigned_url(self, object_name: str, expiration: int = 3600, method: str = "get_object") -> str:
        try:
            return self.client.generate_presigned_url(
                method,
                Params={'Bucket': self.bucket_name, 'Key': object_name},
                ExpiresIn=expiration
            )
        except ClientError as e:
            logger.error(f"Ошибка создания presigned URL: {e}")
            raise

    def get_presigned_upload_url(self, object_name: str, expiration: int = 3600, content_type: str = "application/octet-stream") -> dict:
        try:
            return self.client.generate_presigned_post(
                self.bucket_name,
                object_name,
                Fields={'Content-Type': content_type},
                Conditions=[{'Content-Type': content_type}, ['content-length-range', 0, 100 * 1024 * 1024]],
                ExpiresIn=expiration
            )
        except ClientError as e:
            logger.error(f"Ошибка создания presigned upload URL: {e}")
            raise

    def delete_file(self, object_name: str) -> bool:
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=object_name)
            return True
        except ClientError as e:
            logger.error(f"Ошибка удаления файла: {e}")
            raise

    def list_files(self, prefix: str = "") -> list:
        try:
            response = self.client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
            if 'Contents' not in response:
                return []
            return [
                {
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat(),
                    'etag': obj['ETag']
                }
                for obj in response['Contents']
            ]
        except ClientError as e:
            logger.error(f"Ошибка получения списка файлов: {e}")
            raise

    def file_exists(self, object_name: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=object_name)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise

    def get_file_metadata(self, object_name: str) -> dict:
        try:
            response = self.client.head_object(Bucket=self.bucket_name, Key=object_name)
            return {
                'size': response['ContentLength'],
                'content_type': response.get('ContentType'),
                'last_modified': response['LastModified'].isoformat(),
                'metadata': response.get('Metadata', {}),
                'etag': response['ETag']
            }
        except ClientError as e:
            logger.error(f"Ошибка получения метаданных: {e}")
            raise

    @staticmethod
    def _get_content_type(file_path: Path) -> str:
        extension_map = {
            '.glb': 'model/gltf-binary',
            '.gltf': 'model/gltf+json',
            '.obj': 'text/plain',
            '.fbx': 'application/octet-stream',
            '.stl': 'model/stl',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.json': 'application/json',
        }
        return extension_map.get(file_path.suffix.lower(), 'application/octet-stream')


_s3_instance = None


def get_s3_service() -> S3Service:
    global _s3_instance
    if _s3_instance is None:
        _s3_instance = S3Service()
    return _s3_instance
