"""Append a scene overlay to the reviewed UnityFS player-data format, without building an APK."""

import hashlib
import io
import struct
import zipfile
from pathlib import Path

import lz4.block

from .native import check


def unpack_source(path):
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            return z.read("assets/bin/Data/data.unity3d")
    return Path(path).read_bytes()


def cstr(stream):
    buf = bytearray()
    while (c := stream.read(1)) not in (b"", b"\0"):
        buf.extend(c)
    check(c == b"\0", "Truncated UnityFS name")
    return buf.decode()


def metadata(raw):
    f = io.BytesIO(raw)
    check(
        cstr(f) == "UnityFS" and f.read(4) == struct.pack(">I", 8),
        "Unsupported UnityFS version",
    )
    cstr(f)
    engine = cstr(f)
    header = f.tell()
    length, packed, plain, flags = struct.unpack(">QIII", f.read(20))
    check(
        length == len(raw) and flags == 0xC2 and engine == "6000.3.19f1",
        "Unsupported UnityFS directory",
    )
    meta = io.BytesIO(lz4.block.decompress(raw[-packed:], uncompressed_size=plain))
    check(meta.read(16) == bytes(16), "Unsupported content digest scheme")
    n = struct.unpack(">I", meta.read(4))[0]
    blocks = [struct.unpack(">IIH", meta.read(10)) for _ in range(n)]
    n = struct.unpack(">I", meta.read(4))[0]
    members = {}
    for _ in range(n):
        off, size, flag = struct.unpack(">qqI", meta.read(20))
        name = cstr(meta)
        check(name not in members, "Duplicate Unity member")
        members[name] = (off, size, flag)
    start = (header + 20 + 15) & ~15
    end = len(raw) - packed
    check(
        not meta.read() and sum(c for _, c, _ in blocks) == end - start,
        "Non-contiguous UnityFS blocks",
    )
    return header, start, end, blocks, members


def overlay(raw, scene, registry):
    header, start, end, blocks, members = metadata(raw)
    check(
        "level21" not in members
        and "level20" in members
        and "globalgamemanagers" in members,
        "Map slot collision",
    )
    original_end = sum(n for n, _, _ in blocks)
    extra = bytearray()
    compressed = bytearray()
    for name, data in [("globalgamemanagers", registry), ("level21", scene)]:
        extra.extend(bytes(-(original_end + len(extra)) % 16))
        where = original_end + len(extra)
        extra.extend(data)
        members[name] = (
            where,
            len(data),
            members["level20" if name == "level21" else name][2],
        )
    for i in range(0, len(extra), 131072):
        chunk = extra[i : i + 131072]
        c = lz4.block.compress(chunk, store_size=False)
        if len(c) < len(chunk):
            blocks.append((len(chunk), len(c), 2))
            compressed.extend(c)
        else:
            blocks.append((len(chunk), len(chunk), 0))
            compressed.extend(chunk)
    out = io.BytesIO()
    out.write(bytes(16))
    out.write(struct.pack(">I", len(blocks)))
    for row in blocks:
        out.write(struct.pack(">IIH", *row))
    out.write(struct.pack(">I", len(members)))
    for name, row in members.items():
        out.write(struct.pack(">qqI", *row))
        out.write(name.encode() + b"\0")
    pl = out.getvalue()
    directory = lz4.block.compress(pl, store_size=False)
    head = bytearray(raw[:start])
    struct.pack_into(
        ">QIII",
        head,
        header,
        end + len(compressed) + len(directory),
        len(directory),
        len(pl),
        0xC2,
    )
    return bytes(head) + raw[start:end] + bytes(compressed) + directory


def check_overlay(base, tested, scene, registry):
    import UnityPy

    _, a0, a1, old, mb = metadata(base)
    _, b0, _b1, new, mt = metadata(tested)
    check(
        old == new[: len(old)] and base[a0:a1] == tested[b0 : b0 + a1 - a0],
        "A source block changed",
    )
    check(
        set(mt) == set(mb) | {"level21"}
        and all(mt[n] == v for n, v in mb.items() if n != "globalgamemanagers"),
        "A source asset moved or vanished",
    )
    pack = next(iter(UnityPy.load(tested).files.values()))
    check(set(pack.files) == set(mt), "Unity reader directory mismatch")
    for name, value in [("globalgamemanagers", registry), ("level21", scene)]:
        check(
            pack.files[name].reader.bytes == value, "UnityFS readback mismatch: " + name
        )
    return {
        "unchanged_source_members": len(mb) - 1,
        "unchanged_source_compressed_blocks": len(old),
        "scene_and_registry_read_back": True,
        "integrated_data_sha256": hashlib.sha256(tested).hexdigest(),
    }
