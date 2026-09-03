import os
import sys
import zipfile
import requests
from pathlib import Path

MODEL_DIR = Path.home() / ".EasyOCR" / "model"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

MODELS = [
    {
        "name": "craft_mlt_25k.pth",
        "zip": "craft_mlt_25k.zip",
        "url": "https://github.com/JaidedAI/EasyOCR/releases/download/pre-v1.1.6/craft_mlt_25k.zip"
    },
    {
        "name": "english_g2.pth",
        "zip": "english_g2.zip",
        "url": "https://github.com/JaidedAI/EasyOCR/releases/download/v1.3/english_g2.zip"
    },
    {
        "name": "arabic.pth",
        "zip": "arabic.zip",
        "url": "https://github.com/JaidedAI/EasyOCR/releases/download/pre-v1.1.6/arabic.zip"
    }
]

def download_and_extract(item):
    target_file = MODEL_DIR / item["name"]
    if target_file.exists() and target_file.stat().st_size > 100000:
        print(f"[OK] {item['name']} already exists ({target_file.stat().st_size // 1024} KB)")
        return

    zip_path = MODEL_DIR / item["zip"]
    print(f"Downloading {item['zip']} from {item['url']}...")
    resp = requests.get(item["url"], stream=True, timeout=60)
    resp.raise_for_status()
    total_size = int(resp.headers.get("content-length", 0))
    downloaded = 0
    with open(zip_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 64):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    done = int(50 * downloaded / total_size)
                    sys.stdout.write(f"\r[{'=' * done}{' ' * (50 - done)}] {downloaded * 100 / total_size:.1f}%")
                    sys.stdout.flush()
    print(f"\nExtracting {item['zip']}...")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(MODEL_DIR)
    if zip_path.exists():
        zip_path.unlink()
    print(f"[SUCCESS] {item['name']} ready!")

def main():
    print("Preparing EasyOCR local models in", MODEL_DIR)
    # Remove any stale temp files
    temp_zip = MODEL_DIR / "temp.zip"
    if temp_zip.exists():
        temp_zip.unlink()
    for item in MODELS:
        download_and_extract(item)
    print("All required models are ready for offline inference!")

if __name__ == "__main__":
    main()
