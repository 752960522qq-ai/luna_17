"""Compile BT7_AI as its own stock-compatible Unity serialized file; preserve the eight earlier AI entries."""

import argparse
import json
import zipfile
from pathlib import Path

from ..enemy_prefabs import ALL_DONORS, BASE_SHA, create, one, sha
from ..enemy_verify import verify
from ..enemy_visuals import read_model
from ..unity_assets import Adapter


def writej(p, d):
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prepare(data, hatch, existing_index, out):
    if sha(data) != BASE_SHA:
        raise ValueError("This serializer requires the reviewed 5.1.0 data file")
    out.mkdir(parents=True, exist_ok=True)
    idx = json.loads(existing_index.read_text())
    prev = idx["prefabs"]
    old = [e["id"] for e in prev]
    if (
        idx["stock_data_sha256"] != BASE_SHA
        or len(old) != len(set(old))
        or "BT7" in old
    ):
        raise ValueError("AI index collision or base mismatch")
    a = Adapter(data)
    name = ALL_DONORS["BT7"]
    root = one(
        (
            o.path_id
            for o in a.sf.objects.values()
            if o.type.name == "GameObject"
            and o.read_typetree(check_read=False)["m_Name"] == name
        ),
        name,
    )
    with zipfile.ZipFile(hatch) as mod:
        h = json.loads(mod.read("hatch.json"))
        if h["id"] != "BT7":
            raise ValueError("Wrong vehicle")
        e = create(a, {name: root}, mod, out)
        _, nodes, ims = read_model(mod.read("runtime.bin"), h)
        e["validation"] = verify(a, out / e["file"], e, (nodes, ims, h))
    e["resource_path"] = "unit/so/bt7/bt7_ai"
    e["profile_resource_path"] = "unit/so/bt7/bt7_profile"
    idx["prefabs"] = [*prev, e]
    idx["use"] = (
        "Loose serialized AI prefabs for the named stock build. The BT7 integration kit also registers its root and profile in Resources. Existing entries are unchanged."
    )
    writej(out / "Hatch-Enemy-AI-index.json", idx)
    return e


if __name__ == "__main__":
    c = argparse.ArgumentParser(description=__doc__)
    for n in ("data", "hatch", "existing-index", "out"):
        c.add_argument("--" + n, type=Path, required=True)
    a = c.parse_args()
    e = prepare(a.data, a.hatch, a.existing_index, a.out)
    print(e["file"], e["validation"])
