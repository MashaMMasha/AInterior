import gzip
import io
import json
import pickle
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

import compress_pickle

COMPRESSED_EXTS = {".gz", ".lz4", ".bz2", ".lzma"}

class BaseAssets(ABC):
    @abstractmethod
    def exists(self, relative_path: Path | str) -> bool:
        pass

    @abstractmethod
    def read_bytes(self, relative_path: Path | str) -> bytes:
        pass

    @abstractmethod
    def write_bytes(self, relative_path: Path | str, data: bytes) -> None:
        pass

    @abstractmethod
    def list_files(self, relative_prefix: Path | str = Path()) -> Iterator[Path]:
        pass

    @abstractmethod
    def delete(self, relative_path: Path | str) -> None:
        pass

    @abstractmethod
    def get_local_path(self, relative_path: Path | str) -> Path:
        pass

    @abstractmethod
    def get_local_dir(self, relative_prefix: Path | str) -> Path:
        """
        Возвращает локальный путь к директории (prefix) с ассетами.
        Для удалённых бэкендов (например S3) должен скачать содержимое в кэш.
        """
        pass

    @abstractmethod
    def prepare_local_dir(
        self,
        base_prefix: Path | str,
        subfolders: Iterable[str],
    ) -> Path:
        """
        Подготавливает временную директорию, содержащую только указанные подпапки
        из base_prefix. Возвращает путь ко временной директории.
        Вызывающий код отвечает за очистку (shutil.rmtree).
        """
        pass


    @staticmethod
    def _to_path(relative_path: Path | str) -> Path:
        return Path(relative_path)


    def read_bytes_or_none(self, relative_path: Path | str) -> Optional[bytes]:
        if self.exists(relative_path):
            return self.read_bytes(relative_path)
        return None

    def read_text(self, relative_path: Path | str, encoding: str = "utf-8") -> str:
        return self.read_bytes(relative_path).decode(encoding)

    def write_text(
        self,
        relative_path: Path | str,
        text: str,
        encoding: str = "utf-8",
    ) -> None:
        self.write_bytes(relative_path, text.encode(encoding))


    def read_json(self, relative_path: Path | str, **json_kwargs) -> Any:
        path = self._to_path(relative_path)

        if path.suffix == ".gz":
            raw = self.read_bytes(path)
            decompressed = gzip.decompress(raw)
            return json.loads(decompressed.decode("utf-8"), **json_kwargs)

        return json.loads(self.read_text(path), **json_kwargs)

    def write_json(
        self,
        relative_path: Path | str,
        data: Any,
        indent: Optional[int] = None,
        **json_kwargs,
    ) -> None:
        path = self._to_path(relative_path)

        if path.suffix == ".gz":
            text = json.dumps(data, indent=indent, **json_kwargs).encode("utf-8")
            self.write_bytes(path, gzip.compress(text))
            return

        raw = json.dumps(data, indent=indent, **json_kwargs).encode("utf-8")
        self.write_bytes(path, raw)

    def _get_compression(self, path: Path):
        ext = path.suffix.lstrip(".")
        if ext == "gz":
            return "gzip"
        return ext
        
    def read_pickle(self, relative_path: Path | str, **pickle_kwargs) -> Any:
        path = self._to_path(relative_path)

        if path.suffix in COMPRESSED_EXTS:
            buf = io.BytesIO(self.read_bytes(path))
            return compress_pickle.load(buf, compression=self._get_compression(path), **pickle_kwargs)

        return pickle.loads(self.read_bytes(path), **pickle_kwargs)

    def write_pickle(
        self,
        relative_path: Path | str,
        data: Any,
        **pickle_kwargs,
    ) -> None:
        path = self._to_path(relative_path)

        if path.suffix in COMPRESSED_EXTS:
            buf = io.BytesIO()
            compress_pickle.dump(data, buf, **pickle_kwargs)
            self.write_bytes(path, buf.getvalue())
            return

        self.write_bytes(path, pickle.dumps(data, **pickle_kwargs))


    def upload_from_local(
        self,
        local_path: Path | str,
        relative_path: Path | str,
    ) -> None:
        self.write_bytes(relative_path, Path(local_path).read_bytes())

    def download_to_local(
        self,
        relative_path: Path | str,
        local_path: Path | str,
    ) -> None:
        local = self._to_path(local_path)
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(self.read_bytes(relative_path))
