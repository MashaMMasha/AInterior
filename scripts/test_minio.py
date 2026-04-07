from obllomov.shared.path import HOLODECK_MATERIALS_DIR
from obllomov.storage.assets.s3 import S3Assets

assets = S3Assets()

test_path = HOLODECK_MATERIALS_DIR / "material-database.json"
print(f"Файл существует: {assets.exists(test_path)}")

data = assets.read_json(test_path)
print(f"Ключи: {list(data.keys())[:5]}")
