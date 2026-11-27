"""Offline visual check. Run in Blender 4.3 with an export built with --render-inputs."""

import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

cli = argparse.ArgumentParser(
    description="Render the three Polesie views. Pass arguments after Blender's --"
)
cli.add_argument("--field-dir", required=True, type=Path)
cli.add_argument("--output", required=True, type=Path)
args = cli.parse_args(sys.argv[sys.argv.index("--") + 1 :])
w = args.field_dir
layers = w / "render-layers"
args.output.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(w / "Barbarossa-Polesie.glb"))
s = bpy.context.scene
s.render.engine = "CYCLES"
s.cycles.device = "CPU"
s.cycles.samples = 14
s.cycles.use_denoising = False
s.cycles.max_bounces = 4
s.cycles.transparent_max_bounces = 7
s.render.threads_mode = "FIXED"
s.render.threads = 7
s.render.resolution_x = 1200
s.render.resolution_y = 675
s.render.resolution_percentage = 100
s.render.image_settings.file_format = "PNG"
s.render.image_settings.color_mode = "RGB"
s.view_settings.view_transform = "AgX"
mat = next(m for m in bpy.data.materials if m.name.startswith("Stock meadow"))
nt = mat.node_tree
nodes = nt.nodes
link = nt.links.new
coord = nodes.new("ShaderNodeTexCoord").outputs["UV"]
layer = nodes.new("ShaderNodeTexImage")
layer.image = bpy.data.images.load(str(layers / "splat-view.png"))
layer.image.alpha_mode = "CHANNEL_PACKED"
layer.image.colorspace_settings.name = "Non-Color"
layer.extension = "EXTEND"
link(coord, layer.inputs["Vector"])
se = nodes.new("ShaderNodeSeparateColor")
link(layer.outputs["Color"], se.inputs[0])
out = None
for i, meters in enumerate([5, 10, 9, 9]):
    tile = nodes.new("ShaderNodeTexImage")
    tile.image = bpy.data.images.load(str(layers / f"tile{i}.png"))
    scale = nodes.new("ShaderNodeVectorMath")
    scale.operation = "SCALE"
    link(coord, scale.inputs[0])
    scale.inputs["Scale"].default_value = 1400 / meters
    link(scale.outputs[0], tile.inputs["Vector"])
    part = nodes.new("ShaderNodeVectorMath")
    part.operation = "SCALE"
    link(tile.outputs[0], part.inputs[0])
    link(se.outputs[i] if i < 3 else layer.outputs["Alpha"], part.inputs["Scale"])
    if out is None:
        out = part.outputs[0]
    else:
        add = nodes.new("ShaderNodeVectorMath")
        add.operation = "ADD"
        link(out, add.inputs[0])
        link(part.outputs[0], add.inputs[1])
        out = add.outputs[0]
bs = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
link(out, bs.inputs["Base Color"])
water = next(m for m in bpy.data.materials if m.name.startswith("Daylight water"))
nt = water.node_tree
bs = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
bs.inputs["Roughness"].default_value = 0.37
bs.inputs["Base Color"].default_value = (0.061, 0.15, 0.112, 1)
noise = nt.nodes.new("ShaderNodeTexNoise")
noise.inputs["Scale"].default_value = 1400
noise.inputs["Detail"].default_value = 2.2
uv = nt.nodes.new("ShaderNodeTexCoord")
nt.links.new(uv.outputs["UV"], noise.inputs["Vector"])
bump = nt.nodes.new("ShaderNodeBump")
bump.inputs["Strength"].default_value = 0.13
bump.inputs["Distance"].default_value = 0.09
nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
nt.links.new(bump.outputs[0], bs.inputs["Normal"])
s.world = bpy.data.worlds.new("Summer sky")
s.world.use_nodes = True
bg = s.world.node_tree.nodes.get("Background")
bg.inputs[0].default_value = (0.58, 0.72, 0.87, 1)
bg.inputs[1].default_value = 0.72
# A pale summer horizon and bluer zenith, while diffuse lighting keeps the same stock-tile colours.
nt = s.world.node_tree
tc = nt.nodes.new("ShaderNodeTexCoord")
sp = nt.nodes.new("ShaderNodeSeparateXYZ")
nt.links.new(tc.outputs["Generated"], sp.inputs[0])
ab = nt.nodes.new("ShaderNodeMath")
ab.operation = "ABSOLUTE"
nt.links.new(sp.outputs["Z"], ab.inputs[0])
ramp = nt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.0
ramp.color_ramp.elements[0].color = (0.82, 0.85, 0.78, 1)
ramp.color_ramp.elements[1].position = 0.48
ramp.color_ramp.elements[1].color = (0.24, 0.48, 0.79, 1)
nt.links.new(ab.outputs[0], ramp.inputs[0])
sky = nt.nodes.new("ShaderNodeBackground")
sky.inputs["Strength"].default_value = 0.95
nt.links.new(ramp.outputs[0], sky.inputs[0])
lp = nt.nodes.new("ShaderNodeLightPath")
mix = nt.nodes.new("ShaderNodeMixShader")
nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
nt.links.new(bg.outputs[0], mix.inputs[1])
nt.links.new(sky.outputs[0], mix.inputs[2])
nt.links.new(mix.outputs[0], nt.nodes.get("World Output").inputs[0])
ld = bpy.data.lights.new("Afternoon sun", "SUN")
sun = bpy.data.objects.new("Afternoon sun", ld)
s.collection.objects.link(sun)
sun.rotation_euler = (math.radians(35), math.radians(-28), math.radians(-26))
ld.energy = 3.25
ld.color = (1.0, 0.92, 0.77)
ld.angle = math.radians(2.5)
cam = bpy.data.cameras.new("Field camera")
c = bpy.data.objects.new("Field camera", cam)
s.collection.objects.link(c)
s.camera = c
cam.clip_start = 0.18
cam.clip_end = 2400
import numpy as np

h = np.load(layers / "h.npy") * (64.0 / 32766)


def surface(x, z):
    return float(h[round((z + 700) * 256 / 1400), round((x + 700) * 256 / 1400)])


for name, (x, z, up), (a, b, above), lens in [
    ("village", (-284, -77, 5), (-244, -35, 2.5), 34),
    ("bridge", (103, -83, 17), (156, -23, 1.6), 35),
    ("mill", (322, -322, 9), (331, -273, 4.2), 36),
]:
    loc = Vector((x, z, surface(x, z) + up))
    target = Vector((a, b, surface(a, b) + above))
    c.location = loc
    c.rotation_euler = (target - loc).to_track_quat("-Z", "Y").to_euler()
    cam.lens = lens
    s.render.filepath = str(args.output / (name + ".png"))
    bpy.ops.render.render(write_still=True)
