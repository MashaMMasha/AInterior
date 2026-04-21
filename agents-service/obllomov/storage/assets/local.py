from pathlib import Path
from typing import Iterator, Optional

from obllomov.shared.env import env

from .base import BaseAssets


class LocalAssets(BaseAssets):

    def __init__(self, root_dir: Path | str | None = None) -> None:
        if root_dir is None:
            root_dir = env.OBJATHOR_ASSETS_BASE_DIR
        self.root_dir = Path(root_dir).expanduser().resolve()


    def _abs(self, relative_path: Path | str) -> Path:
        return self.root_dir / relative_path

    def exists(self, relative_path: Path | str) -> bool:
        return self._abs(relative_path).is_file()

    def read_bytes(self, relative_path: Path | str) -> bytes:
        return self._abs(relative_path).read_bytes()

    # def read_bytes_or_none(self, relative_path: Path | str) -> Optional[bytes]:
    #     abs_path = self._abs(relative_path)
    #     try:
    #         return abs_path.read_bytes()
    #     except (FileNotFoundError, IsADirectoryError):
    #         return None

    def write_bytes(self, relative_path: Path | str, data: bytes) -> None:
        abs_path = self._abs(relative_path)
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_bytes(data)

    def list_files(self, relative_prefix: Path | str = Path()) -> Iterator[Path]:
        base = self._abs(relative_prefix)
        if not base.exists():
            return
        for path in base.rglob("*"):
            if path.is_file():
                yield path.relative_to(self.root_dir)

    def delete(self, relative_path: Path | str) -> None:
        self._abs(relative_path).unlink(missing_ok=True)

    def get_local_path(self, relative_path: Path | str) -> Path:
        abs_path = self._abs(relative_path)
        if not abs_path.is_file():
            raise FileNotFoundError(
                f"Файл не найден в локальном хранилище: {abs_path}"
            )
        return abs_path

    def get_local_dir(self, relative_prefix: Path | str) -> Path:
        abs_path = self._abs(relative_prefix)
        if not abs_path.is_dir():
            raise FileNotFoundError(
                f"Директория не найдена в локальном хранилище: {abs_path}"
            )
        return abs_path
