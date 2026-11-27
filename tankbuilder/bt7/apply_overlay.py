"""Extract the verified Unity player data with the BT-7 registered. Python standard library only."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


def assemble(src, out, folder):
    spec = json.loads((folder / "integration.json").read_text())
    delta = (folder / "BT7.overlay").read_bytes()
    sha = lambda b: hashlib.sha256(b).hexdigest()
    if src.resolve() == out.resolve() or out.exists():
        raise ValueError("Choose a new output file; the source is never overwritten")
    if zipfile.is_zipfile(src):
        with zipfile.ZipFile(src) as a:
            raw = a.read("assets/bin/Data/data.unity3d")
    else:
        raw = src.read_bytes()
    if sha(raw) != spec["base_sha256"] or sha(delta) != spec["overlay_sha256"]:
        raise ValueError("Base game or overlay checksum differs from this release")
    head = spec["header_bytes"]
    result = (
        delta[:head] + raw[spec["retain_start"] : spec["retain_end"]] + delta[head:]
    )
    if sha(result) != spec["result_sha256"]:
        raise ValueError("Assembled data mismatch")
    out.parent.mkdir(exist_ok=True, parents=True)
    with out.open("xb") as f:
        f.write(result)
    return spec["result_sha256"]


if __name__ == "__main__":
    c = argparse.ArgumentParser(description=__doc__)
    c.add_argument("source", type=Path)
    c.add_argument("output", type=Path)
    a = c.parse_args()
    print(assemble(a.source, a.output, Path(__file__).resolve().parent))
