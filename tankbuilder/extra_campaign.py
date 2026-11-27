"""Prepare the original-GUI extra campaign menu in level0; never build an APK."""

import argparse
import copy
import hashlib
import struct
import zipfile
from pathlib import Path

import UnityPy

from .campaign_ugui import PTR, clone_component, require
from .serialization import apply_reviewed_typetrees, assert_roundtrip, encode_complete
from .unity_assets import EditableObject, pp

DIGESTS = {
    "level0": "986b3538ae7ff2eba4a8c9f3cc59e4804a0bcec4a4550be1a8d75478194ed257",
    "level1": "cbc9dfdacd41c77edb385a69442e6240f108af7c93445bcbd8ddb2712052d1e9",
    "globalgamemanagers.assets": "b5be6bf2c1de6999f9433d13465af34389771947286414e92c5768f64181de0a",
}
LABEL, TITLE, EMPTY = "额外战役", "巴巴罗萨行动", "暂无可用任务"
ENTRY, PANEL, HOME, RAIL, LIST = 426, 205, 337, 212, 277
PAGE, BLOCKER, HEADING, TITLE_CN, SLOTS, SLOT, EMPTY_TEXT, BACK = (
    1046,
    582,
    563,
    286,
    569,
    2910,
    303,
    559,
)
ENTRY_NODES = (ENTRY, 394, 380, 46, 469, 224)
PAGE_NODES = (PAGE, BLOCKER, HEADING, TITLE_CN, SLOTS, SLOT, EMPTY_TEXT, BACK)
ORIGINAL_MENU = (ENTRY, 681, 680, 684, 683, 682)
ENTRY_NAME, PAGE_NAME = "Hatch Extra Campaign", "Hatch Extra Campaign Page"
ARCHIVE_PATH = "assets/bin/Data/data.unity3d"


def inputs(path):
    if path.is_dir():
        return {k: (path / k).read_bytes() for k in DIGESTS}
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as apk:
            data = apk.read(ARCHIVE_PATH)
    else:
        data = path.read_bytes()
    archive = next(iter(UnityPy.load(data).files.values()))
    return {k: archive.files[k].reader.bytes for k in DIGESTS}


def file(raw):
    env = UnityPy.load(raw)
    apply_reviewed_typetrees(env)
    return next(iter(env.files.values()))


class Scene:
    def __init__(self, sf, scripts):
        self.sf = sf
        self.names = scripts
        self.go, self.rect, self.part = {}, {}, {}
        for pid, obj in sf.objects.items():
            if obj.type.name != "GameObject":
                continue
            go = self.go[pid] = assert_roundtrip(obj)
            self.part[pid] = {}
            for component in go["m_Component"]:
                c = component["component"]["m_PathID"]
                kind = self.kind(sf.objects[c])
                # Only look up unique component types on the selected GUI nodes.
                self.part[pid].setdefault(kind, c)
                if kind == "RectTransform":
                    self.rect[pid] = c

    def kind(self, obj):
        if obj.type.name != "MonoBehaviour":
            return obj.type.name
        fid, pid = PTR.unpack_from(obj.get_raw_data(), 16)
        require(
            fid > 0 and self.sf.externals[fid - 1].path == "globalgamemanagers.assets",
            "Unexpected script file",
        )
        return self.names[pid]

    def transform(self, go):
        return assert_roundtrip(self.sf.objects[self.rect[go]])

    def children(self, go):
        return [
            assert_roundtrip(self.sf.objects[c["m_PathID"]])["m_GameObject"]["m_PathID"]
            for c in self.transform(go)["m_Children"]
        ]


def scenes(data):
    for k, digest in DIGESTS.items():
        require(
            hashlib.sha256(data[k]).hexdigest() == digest,
            f"Unexpected {k}; refusing to edit an unreviewed UI scene",
        )
    scripts = {
        p: o.read_typetree(check_read=False)["m_ClassName"]
        for p, o in file(data["globalgamemanagers.assets"]).objects.items()
        if o.type.name == "MonoScript"
    }
    return Scene(file(data["level0"]), scripts), Scene(file(data["level1"]), scripts)


def map_tree(value, ref):
    if isinstance(value, dict):
        if set(value) == {"m_FileID", "m_PathID"}:
            f, p = ref(value["m_FileID"], value["m_PathID"])
            return pp(p, f)
        return {k: map_tree(v, ref) for k, v in value.items()}
    if isinstance(value, list):
        return [map_tree(v, ref) for v in value]
    if isinstance(value, tuple):
        return tuple(map_tree(v, ref) for v in value)
    return value


def put(sf, template, pid, raw):
    concrete_type = template.serialized_type
    index = next(
        i
        for i, t in enumerate(sf.types)
        if (t.class_id, t.script_id, t.old_type_hash)
        == (
            concrete_type.class_id,
            concrete_type.script_id,
            concrete_type.old_type_hash,
        )
    )
    obj = object.__new__(EditableObject)
    obj.__dict__.update(template.__dict__)
    obj.assets_file, obj.path_id, obj.type_id, obj.serialized_type = (
        sf,
        pid,
        index,
        sf.types[index],
    )
    obj.set_raw_data(raw)
    sf.objects[pid] = obj


def prepare(data):
    home, stage = scenes(data)
    sf = home.sf
    require(home.children(LIST) == list(ORIGINAL_MENU), "Unexpected home menu order")
    # Retain all stock button presentation, exclude only the old localization key / game actions.
    excluded = {"LeanLocalizedText", "StageSelectUiManager"}
    id_maps, kinds = {}, {}
    next_id = max(sf.objects) + 1
    for sc, selected in [(home, ENTRY_NODES), (stage, PAGE_NODES)]:
        ids = id_maps[sc] = {}
        for go in selected:
            for pid in [
                go,
                *[c["component"]["m_PathID"] for c in sc.go[go]["m_Component"]],
            ]:
                kind = sc.kind(sc.sf.objects[pid])
                if kind in excluded or (
                    sc is stage and go == SLOT and kind == "Button"
                ):
                    continue
                ids[pid], kinds[sc, pid] = next_id, kind
                next_id += 1
    hm, sm = id_maps[home], id_maps[stage]
    open_calls = [
        (sm[PAGE], True),
        (RAIL, False),
        (HOME, False),
        (sm[stage.part[BACK]["Button"]], None),
    ]
    back_calls = [
        (HOME, True),
        (RAIL, True),
        (sm[PAGE], False),
        (hm[home.part[ENTRY]["Button"]], None),
    ]
    ordered_children = {
        PAGE: [BLOCKER, HEADING, SLOTS, BACK],
        BLOCKER: [],
        HEADING: [TITLE_CN],
        TITLE_CN: [],
        SLOTS: [SLOT],
        SLOT: [EMPTY_TEXT],
        EMPTY_TEXT: [],
        BACK: [],
    }
    stage_parent = {
        child: parent for parent, kids in ordered_children.items() for child in kids
    }
    stock_font = PTR.unpack_from(
        stage.sf.objects[stage.part[TITLE_CN]["Text"]].get_raw_data(), 88
    )
    slot_tint = struct.unpack_from(
        "<4f", stage.sf.objects[stage.part[SLOT]["Button"]].get_raw_data(), 92
    )
    for sc, selected in [(home, ENTRY_NODES), (stage, PAGE_NODES)]:
        ids = id_maps[sc]

        def ref(fid, pid, *, ids=ids, sc=sc):
            if fid == 0:
                require(
                    pid == 0 or pid in ids,
                    f"Unexpected reference outside cloned hierarchy: {pid}",
                )
                return 0, ids.get(pid, 0)
            ext = sc.sf.externals[fid - 1]
            for index, dest in enumerate(sf.externals, 1):
                if dest.path == ext.path:
                    require(
                        dest.guid == ext.guid and dest.type == ext.type,
                        "Incompatible shared asset",
                    )
                    return index, pid
            require(
                ext.path == "sharedassets1.assets", "Unexpected new scene dependency"
            )
            sf.externals.append(copy.copy(ext))
            return len(sf.externals), pid

        for go in selected:
            source_go = sc.go[go]
            components = [
                c["component"]["m_PathID"]
                for c in source_go["m_Component"]
                if c["component"]["m_PathID"] in ids
            ]
            for pid in [go, *components]:
                obj = sc.sf.objects[pid]
                kind = kinds[sc, pid]
                if kind == "GameObject":
                    v = {
                        **source_go,
                        "m_Component": [{"component": pp(ids[c])} for c in components],
                    }
                    if (sc is home and go == ENTRY) or (sc is stage and go == PAGE):
                        v["m_Name"] = ENTRY_NAME if sc is home else PAGE_NAME
                    if sc is stage:
                        v["m_IsActive"] = go != PAGE
                        if go == BLOCKER:
                            v["m_Name"] = "Backdrop"
                    raw = encode_complete(obj, v)
                elif kind == "RectTransform":
                    v = sc.transform(go)
                    if sc is home:
                        v["m_Father"] = pp(
                            home.rect[LIST]
                            if go == ENTRY
                            else ids[v["m_Father"]["m_PathID"]]
                        )
                        v["m_Children"] = [
                            pp(ids[c["m_PathID"]]) for c in v["m_Children"]
                        ]
                        if go == ENTRY:
                            v["m_SizeDelta"]["y"] = 44.0
                    else:
                        v["m_Father"] = pp(
                            home.rect[PANEL]
                            if go == PAGE
                            else ids[sc.rect[stage_parent[go]]]
                        )
                        v["m_Children"] = [
                            pp(ids[sc.rect[ch]]) for ch in ordered_children[go]
                        ]
                        if go == TITLE_CN:
                            v["m_SizeDelta"] = {"x": 440.0, "y": 60.0}
                        if go == BLOCKER:
                            v["m_AnchoredPosition"] = {"x": 0.0, "y": 0.0}
                            v["m_SizeDelta"] = {"x": 0.0, "y": 0.0}
                    v["m_GameObject"] = pp(ids[go])
                    raw = encode_complete(obj, v)
                elif obj.type.name == "MonoBehaviour":
                    label = (
                        LABEL if sc is home else (TITLE if go == TITLE_CN else EMPTY)
                    )
                    raw = clone_component(
                        kind,
                        obj.get_raw_data(),
                        ref,
                        label=label,
                        font=stock_font
                        if sc is stage and go == EMPTY_TEXT and kind == "Text"
                        else None,
                        clicks=open_calls
                        if go == ENTRY and sc is home
                        else (back_calls if go == BACK and sc is stage else None),
                        tint=(slot_tint if go == SLOT else (0.0, 0.0, 0.0, 0.35))
                        if sc is stage and go in (SLOT, BLOCKER) and kind == "Image"
                        else None,
                    )
                else:
                    raw = encode_complete(obj, map_tree(assert_roundtrip(obj), ref))
                put(sf, obj, ids[pid], raw)

    def insert(parent, sibling, new_rect):
        obj = sf.objects[home.rect[parent]]
        v = assert_roundtrip(obj)
        children = v["m_Children"]
        children.insert(children.index(pp(home.rect[sibling])) + 1, pp(new_rect))
        put(sf, obj, obj.path_id, encode_complete(obj, v))

    insert(LIST, ENTRY, hm[home.rect[ENTRY]])
    insert(PANEL, HOME, sm[stage.rect[PAGE]])
    for go in ORIGINAL_MENU:
        obj = sf.objects[home.rect[go]]
        v = assert_roundtrip(obj)
        require(v["m_SizeDelta"]["y"] == 50.0, "Unexpected stock menu item height")
        v["m_SizeDelta"]["y"] = 44.0
        put(sf, obj, obj.path_id, encode_complete(obj, v))
    layout = sf.objects[home.part[LIST]["VerticalLayoutGroup"]]
    raw = bytearray(layout.get_raw_data())
    require(
        len(raw) == 84
        and struct.unpack_from("<5if", raw, 32) == (65, 0, 190, 10, 3, 5.0),
        "Unknown menu layout",
    )
    struct.pack_into(
        "<f", raw, 52, 4.0
    )  # Seven stock-font rows, clear of logo and safe-area bottom.
    put(sf, layout, layout.path_id, raw)
    return sf.save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Hatch APK, its data.unity3d, or a directory of original loose Unity files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="staging directory; writes level0 only",
    )
    args = parser.parse_args()
    if args.source.is_dir():
        require(
            args.source.resolve() != args.output.resolve(),
            "Use a separate staging directory",
        )
    raw = prepare(inputs(args.source))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "level0").write_bytes(raw)
    print(f"level0: {len(raw)} bytes, SHA-256 {hashlib.sha256(raw).hexdigest()}")


if __name__ == "__main__":
    main()
