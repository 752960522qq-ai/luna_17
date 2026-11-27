"""Narrow UGUI codecs for the fingerprinted 5.1.0 player scenes (little-endian)."""

import struct

PTR = struct.Struct("<iq")
GO_TYPE = "UnityEngine.GameObject, UnityEngine.CoreModule"
BUTTON_TYPE = "UnityEngine.UI.Button, UnityEngine.UI"
OBJECT_TYPE = "UnityEngine.Object, UnityEngine"


def require(value, message):
    if not value:
        raise ValueError(message)


def i32(raw, pos):
    return struct.unpack_from("<i", raw, pos)[0]


def string(value):
    b = value.encode("utf-8")
    return struct.pack("<i", len(b)) + b + bytes(-len(b) % 4)


def read_string(raw, pos):
    length = i32(raw, pos)
    start = pos + 4
    end = (start + length + 3) & ~3
    require(0 <= length and end <= len(raw), "Invalid Unity string")
    return bytes(raw[start : start + length]).decode("utf-8"), end


def button_event(raw):
    # Navigation, ColorBlock and SpriteState are followed by the five animation triggers.
    at = 228
    for _ in range(5):
        _, at = read_string(raw, at)
    target_offset = at + 4  # m_Interactable precedes targetGraphic
    event_offset = target_offset + PTR.size
    count = i32(raw, event_offset)
    require(0 <= count <= 16, "Unexpected persistent call count")
    at = event_offset + 4
    calls = []
    for _ in range(count):
        target = PTR.unpack_from(raw, at)
        cls, at = read_string(raw, at + PTR.size)
        method, at = read_string(raw, at)
        mode = i32(raw, at)
        obj = PTR.unpack_from(raw, at + 4)
        arg_type, at = read_string(raw, at + 4 + PTR.size)
        int_arg, float_arg = struct.unpack_from("<if", raw, at)
        str_arg, at = read_string(raw, at + 8)
        bool_arg, state = struct.unpack_from("<ii", raw, at)
        at += 8
        calls.append(
            (
                target,
                cls,
                method,
                mode,
                obj,
                arg_type,
                int_arg,
                float_arg,
                str_arg,
                bool_arg,
                state,
            )
        )
    require(at == len(raw), "Unexpected Button.onClick tail")
    return target_offset, event_offset, calls


def write_calls(calls):
    out = bytearray(struct.pack("<i", len(calls)))
    for target, enabled in calls:
        select = enabled is None
        out += PTR.pack(0, target) + string(BUTTON_TYPE if select else GO_TYPE)
        out += string("Select" if select else "SetActive") + struct.pack(
            "<i", 1 if select else 6
        )
        out += (
            PTR.pack(0, 0) + string(OBJECT_TYPE) + struct.pack("<if", 0, 0) + string("")
        )
        out += struct.pack("<ii", int(bool(enabled)), 2)  # RuntimeOnly
    return out


def text_value(raw):
    value, end = read_string(raw, 144)
    require(end == len(raw), "Unexpected legacy Text layout")
    return value


def clone_component(kind, src, ref, *, label=None, font=None, clicks=None, tint=None):
    """Map typed PPtrs only. Refuse to inherit unknown behaviours or UnityEvents."""
    raw = bytearray(src)
    require(i32(raw, 28) == 0, "Expected empty MonoBehaviour name")
    offsets = [0, 16]  # GameObject owner and MonoScript
    if kind in ("Image", "Text"):
        require(i32(raw, 84) == 0, "Unexpected graphic cull listener")
        offsets += [32, 88]  # graphic material, followed by sprite/legacy font
        if kind == "Image":
            require(len(raw) == 136, "Unexpected Image layout")
        else:
            text_value(raw)
            require(label is not None, "Expected explicit label")
            raw[144:] = string(label)
            if font is not None:
                PTR.pack_into(raw, 88, *font)
        if tint is not None:
            struct.pack_into("<4f", raw, 44, *tint)
    elif kind == "Button":
        target, event, original = button_event(raw)
        require(
            len(original) == 1 and clicks is not None,
            "Expected to replace one stock action",
        )
        offsets += [40, 52, 64, 76, 180, 192, 204, 216, target]
        raw[event:] = write_calls(clicks)
        button_event(raw)
    else:
        lengths = {
            "GradientColor": 44,
            "Shadow": 60,
            "Outline": 60,
            "ButtonAnimationFix": 32,
            "UIElementSound": 88,
        }
        require(
            kind in lengths and len(raw) == lengths[kind],
            f"Unhandled component layout: {kind}",
        )
        if kind == "UIElementSound":
            offsets += [32, 44, 56, 68]
    for at in offsets:
        PTR.pack_into(raw, at, *ref(*PTR.unpack_from(raw, at)))
    return bytes(raw)
