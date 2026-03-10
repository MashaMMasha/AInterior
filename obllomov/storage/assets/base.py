import io
import json
import pickle
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Iterator, Optional

import compress_json
import compress_pickle


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


    @staticmethod
    def _to_path(relative_path: Path | str) -> Path:
        return Path(relative_path)


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
            buf = io.BytesIO(self.read_bytes(path))
            return compress_json.load(buf, **json_kwargs)

        return json.loads(self.read_bytes(path), **json_kwargs)

    def write_json(
        self,
        relative_path: Path | str,
        data: Any,
        indent: Optional[int] = None,
        **json_kwargs,
    ) -> None:
        path = self._to_path(relative_path)

        if path.suffix == ".gz":
            buf = io.BytesIO()
            compress_json.dump(data, buf, json_kwargs={"indent": indent, **json_kwargs})
            self.write_bytes(path, buf.getvalue())
            return

        raw = json.dumps(data, indent=indent, **json_kwargs).encode("utf-8")
        self.write_bytes(path, raw)


    def read_pickle(self, relative_path: Path | str, **pickle_kwargs) -> Any:
        path = self._to_path(relative_path)
        compressed_exts = {".gz", ".lz4", ".bz2", ".lzma"}

        if path.suffix in compressed_exts:
            buf = io.BytesIO(self.read_bytes(path))
            return compress_pickle.load(buf, **pickle_kwargs)

        return pickle.loads(self.read_bytes(path), **pickle_kwargs)

    def write_pickle(
        self,
        relative_path: Path | str,
        data: Any,
        **pickle_kwargs,
    ) -> None:
        path = self._to_path(relative_path)
        compressed_exts = {".gz", ".lz4", ".bz2", ".lzma"}

        if path.suffix in compressed_exts:
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
