"""Fetch the pinned official engine and only Android files from the template ZIP.

No pip dependencies. Uses HTTP range reads to avoid downloading templates for
unrelated platforms. Run from the repository root: python scripts/fetch_godot.py
"""

import hashlib
import io
import json
from pathlib import Path
import shutil
import urllib.request
import zipfile

VERSION = "4.7.2"
ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".tools" / "godot"
BASE = f"https://github.com/godotengine/godot-builds/releases/download/{VERSION}-stable/"


def request(url, headers=None):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Maze-prototype-build", **(headers or {})}), timeout=120)


class RemoteZip(io.RawIOBase):
    """Seekable HTTP object. Refuses servers which ignore the Range header."""

    def __init__(self, url, size):
        self.url = url
        self.size = size
        self.position = 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        self.position = offset if whence == 0 else self.position + offset if whence == 1 else self.size + offset
        return self.position

    def read(self, size=-1):
        end = self.size if size < 0 else min(self.size, self.position + size)
        if end <= self.position:
            return b""
        with request(self.url, {"Range": f"bytes={self.position}-{end - 1}"}) as response:
            if response.status != 206:
                raise RuntimeError("Template server does not support partial downloads.")
            data = response.read()
        if len(data) != end - self.position:
            raise RuntimeError("Incomplete HTTP range response.")
        self.position = end
        return data


def main():
    TOOLS.mkdir(parents=True, exist_ok=True)
    engine_name = f"Godot_v{VERSION}-stable_win64.exe.zip"
    engine = TOOLS / engine_name.removesuffix(".zip")
    with request(f"https://api.github.com/repos/godotengine/godot-builds/releases/tags/{VERSION}-stable") as response:
        release = json.load(response)
    assets = {asset["name"]: asset for asset in release["assets"]}
    if not engine.exists():
        archive = TOOLS / engine_name
        print("Downloading official Godot engine…", flush=True)
        with request(BASE + engine_name) as response, archive.open("wb") as target:
            shutil.copyfileobj(response, target)
        with request(BASE + "SHA512-SUMS.txt") as response:
            sums = response.read().decode()
        expected = next(line.split()[0] for line in sums.splitlines() if line.endswith(engine_name))
        if hashlib.sha512(archive.read_bytes()).hexdigest() != expected:
            raise RuntimeError("Engine SHA512 verification failed.")
        with zipfile.ZipFile(archive) as bundle:
            for name in bundle.namelist():
                if "/" not in name and name.endswith(".exe"):
                    bundle.extract(name, TOOLS)
    template_name = f"Godot_v{VERSION}-stable_export_templates.tpz"
    template = TOOLS / "android_debug.apk"
    if not template.exists():
        print("Downloading Android debug template only…", flush=True)
        remote = RemoteZip(BASE + template_name, assets[template_name]["size"])
        with zipfile.ZipFile(remote) as bundle:
            # ZipFile validates the member CRC before accepting its contents.
            data = bundle.read("templates/android_debug.apk")
        template.write_bytes(data)
    print(f"Engine: {engine}")
    print(f"Android template: {template}")


if __name__ == "__main__":
    main()
