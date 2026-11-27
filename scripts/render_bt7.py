"""Render the actual Hatch vehicle GLB; optional moving rig reel uses the same radii and tread period as Hatch."""

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Quaternion, Vector

cli = argparse.ArgumentParser()
cli.add_argument("--project", type=Path, required=True)
cli.add_argument("--out", type=Path, required=True)
cli.add_argument("--motion", action="store_true")
args = cli.parse_args(sys.argv[sys.argv.index("--") + 1 :])
vehicle = json.loads((args.project / "manifest.json").read_text())["id"]
is_f = vehicle == "Panzer_II_Ausf_F"
is_c = vehicle == "Panzer_IV_Ausf_C"
out = args.out
out.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(args.project.resolve() / "model.glb"))
s = bpy.context.scene
s.render.engine = "CYCLES"
s.cycles.samples = 32 if is_f else 20
s.cycles.use_denoising = False
s.cycles.max_bounces = 4
s.render.threads_mode = "FIXED"
s.render.threads = 7
s.render.resolution_x = 1152
s.render.resolution_y = 720
s.render.resolution_percentage = 100
s.render.image_settings.file_format = "PNG"
s.render.image_settings.color_mode = "RGB"
s.view_settings.view_transform = "AgX"
model_objects = list(s.objects)
for o in model_objects:
    if o.animation_data:
        for tr in o.animation_data.nla_tracks:
            tr.mute = True
        o.animation_data.action = None
    if o.type == "MESH" and o.name.startswith("Icosphere"):
        o.hide_render = True
world = s.world = bpy.data.worlds.new("Studio fill")
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs[0].default_value = (0.61, 0.69, 0.72, 1)
bg.inputs[1].default_value = 0.50


def light(n, at, power, size, hue):
    data = bpy.data.lights.new(n, "AREA")
    o = bpy.data.objects.new(n, data)
    s.collection.objects.link(o)
    o.location = at
    o.rotation_euler = (
        (Vector((0, 0, 0.9)) - o.location).to_track_quat("-Z", "Y").to_euler()
    )
    data.energy = power
    data.shape = "DISK"
    data.size = size
    data.color = hue


light("Softbox", (-4.5, 5.7, 7.8), 1020, 5.8, (1, 0.91, 0.76))
light("Side fill", (6, 2, 5), 730, 5, (0.82, 0.89, 1))
light("Rim", (-0.4, -7, 6), 1280, 5.3, (1, 0.94, 0.84))
bpy.ops.mesh.primitive_plane_add(size=300, location=(0, 0, -0.018))
floor = bpy.context.object
mat = bpy.data.materials.new("Warm grey backdrop")
mat.use_nodes = True
bs = mat.node_tree.nodes.get("Principled BSDF")
bs.inputs["Base Color"].default_value = (0.17, 0.18, 0.156, 1)
bs.inputs["Roughness"].default_value = 1.0
floor.data.materials.append(mat)
cam = bpy.data.cameras.new("Camera")
c = bpy.data.objects.new("Camera", cam)
s.collection.objects.link(c)
s.camera = c
cam.type = "ORTHO"


def camera(position, look, size):
    c.location = position
    c.rotation_euler = (
        (Vector(look) + Vector((0, 0, 0.23 if is_f or is_c else 0)) - c.location)
        .to_track_quat("-Z", "Y")
        .to_euler()
    )
    cam.ortho_scale = size * (0.90 if is_f else 1.09 if is_c else 1.0)


def shot(name):
    s.render.filepath = str((out / (name + ".png")).resolve())
    bpy.ops.render.render(write_still=True)


camera((-6.2, 7.3, 4.05), (0, 0, 1.0), 7.10)
shot("Front")
camera((-8, 1.7, 2.65), (0, 0, 1.11), 6.95)
shot("Running-gear")
camera((6.3, -6.2, 4.0), (0, 0, 1.07), 7.05)
shot("Rear")
if args.motion:
    rig = json.loads((args.project / "rig.json").read_text())
    arm = next(o for o in model_objects if o.type == "ARMATURE")

    def basis(o):
        # Convert a world axis to the object's local rest coordinates, for Blender's imported bone parents.
        bpy.context.view_layer.update()
        return o.matrix_world.to_quaternion().inverted()

    rotations = {}
    world_dirs = {}
    for objname in [w["name"] for w in rig["wheels"]] + ["Turret", "Gun"]:
        o = bpy.data.objects[objname]
        o.rotation_mode = "QUATERNION"
        rotations[objname] = o.rotation_quaternion.copy()
        world_dirs[objname] = basis(o)
    recoil = bpy.data.objects["Barrel_Recoil"]
    restpos = recoil.location.copy()
    local_back = basis(recoil.parent) @ Vector((0, -1, 0))
    road = [w for w in rig["wheels"] if w["roadWheel"]]
    bones = {w["name"]: arm.pose.bones["Suspension_" + w["name"]] for w in road}
    up = {
        name: (arm.matrix_world @ bo.matrix).to_quaternion().inverted()
        @ Vector((0, 0, 1))
        for name, bo in bones.items()
    }
    scroll = []
    for suffix in ("l", "r"):
        mat = bpy.data.materials[
            ("Pz2F" if is_f else "Pz4C" if is_c else "BT7") + "_tread_" + suffix
        ]
        nt = mat.node_tree
        tex = next(n for n in nt.nodes if n.type == "TEX_IMAGE")
        old = tex.inputs["Vector"].links
        coord = (
            old[0].from_socket
            if old
            else nt.nodes.new("ShaderNodeTexCoord").outputs["UV"]
        )
        add = nt.nodes.new("ShaderNodeVectorMath")
        add.operation = "ADD"
        nt.links.new(coord, add.inputs[0])
        nt.links.new(add.outputs[0], tex.inputs["Vector"])
        scroll.append(add.inputs[1])
    s.render.resolution_x = 768
    s.render.resolution_y = 432
    s.cycles.samples = 8 if is_f else 6
    s.render.fps = 18
    # Forward, reverse, then counter-rotation on a marked inspection floor.
    D = [0.0, 0.0]
    N = 108
    folder = out / "frames"
    folder.mkdir(exist_ok=True)
    for f in range(N):
        t = f / 18
        speed = (0.78, 0.78) if t < 2 else ((-0.62, -0.62) if t < 4 else (-0.64, 0.64))
        if f:
            for j in (0, 1):
                D[j] += speed[j] / 18
        for w in rig["wheels"]:
            nm = w["name"]
            j = 0 if w["side"] == "left" else 1
            bpy.data.objects[nm].rotation_quaternion = rotations[nm] @ Quaternion(
                world_dirs[nm] @ Vector((1, 0, 0)), -D[j] / w["radius"]
            )
        for j in (0, 1):
            scroll[j].default_value = (0, D[j] / rig["trackLoopMeters"], 0)
        for w in road:
            nm = w["name"]
            h = (
                0.041
                * math.sin(math.pi * t / 3)
                * math.sin(t * 4.6 + w["center"][2] * 2.2)
            )
            bones[nm].location = up[nm] * h
        yaw = math.radians(23) * math.sin(t * math.pi / 3)
        pitch = math.radians(10) * (0.5 - 0.5 * math.cos(t * math.pi / 2.7))
        for nm, axis, val in [("Turret", (0, 0, 1), yaw), ("Gun", (1, 0, 0), pitch)]:
            bpy.data.objects[nm].rotation_quaternion = rotations[nm] @ Quaternion(
                world_dirs[nm] @ Vector(axis), val
            )
        kick = max(0, 1 - abs(t - 3.0) / 0.16)
        if is_f:
            kick = max(
                (max(0, 1 - abs(t - at) / 0.10) for at in (2.2, 2.6, 3.0, 3.4, 3.8)),
                default=0,
            )
        recoil.location = restpos + local_back * rig["gun"]["recoil"] * kick
        a = math.radians(36 - 21 * t / 6)
        camera(
            (-8 * math.cos(a), 8 * math.sin(a), 3.1 + 0.34 * math.cos(t / 1.4)),
            (0, 0, 1.06),
            7.1,
        )
        s.render.filepath = str((folder / f"{f:04}.png").resolve())
        bpy.ops.render.render(write_still=True)
