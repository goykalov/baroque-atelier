"""Render an automatically framed view of a metre-scaled, Z-up room OBJ."""
import argparse
import math
from pathlib import Path
import sys
import bpy
from mathutils import Vector

parser = argparse.ArgumentParser()
parser.add_argument("source", type=Path)
parser.add_argument("output", type=Path)
parser.add_argument("--draft", action="store_true")
parser.add_argument("--detail", action="store_true")
parser.add_argument("--ceiling", action="store_true")
parser.add_argument("--opposite", action="store_true")
parser.add_argument("--editorial", action="store_true")
parser.add_argument("--cpu", action="store_true")
parser.add_argument("--width", type=int, help="Horizontal image size in pixels.")
parser.add_argument("--samples", type=int, help="Maximum number of Cycles samples.")
options = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
if options.width is not None and options.width < 16:
    parser.error("--width must be at least 16")
if options.samples is not None and options.samples < 1:
    parser.error("--samples must be positive")
source, output = options.source.resolve(), options.output.resolve()
quick = options.draft
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
bpy.ops.wm.obj_import(filepath=str(source), forward_axis="Y", up_axis="Z")
bpy.context.view_layer.update()


def tag_name(name):
    return name.split(".", 1)[0]


def bounds(obj):
    corners = [obj.matrix_world @ Vector(v) for v in obj.bound_box]
    return (tuple(min(p[k] for p in corners) for k in range(3)),
            tuple(max(p[k] for p in corners) for k in range(3)))


meshes = [obj for obj in scene.objects if obj.type == "MESH" and len(obj.data.vertices)]
floor = [obj for obj in meshes if obj.name.startswith("Паркет")]
floor = floor or meshes
limits = [bounds(obj) for obj in floor]
x0, y0, z0 = (min(lo[k] for lo, hi in limits) for k in range(3))
x1, y1 = (max(hi[k] for lo, hi in limits) for k in range(2))
height = max(bounds(obj)[1][2] for obj in meshes) - z0
length, width = x1 - x0, y1 - y0
cx, cy = (x0 + x1) / 2, (y0 + y1) / 2


def position(x, y, z):
    return (cx + length*x, cy + width*y, z0 + height*z)


def point_at(obj, where):
    obj.rotation_euler = (Vector(where) - obj.location).to_track_quat("-Z", "Y").to_euler()


def linear(value):
    return value / 12.92 if value <= .04045 else ((value+.055)/1.055)**2.4


def finish_material(mat):
    tag = tag_name(mat.name)
    mat.use_nodes = True
    tree = mat.node_tree
    shader = tree.nodes.get("Principled BSDF")
    if shader is None:
        return
    base = shader.inputs["Base Color"]
    original = tuple(base.default_value)[:3]
    # OBJ Kd in this project is the sRGB palette value.
    base.default_value = tuple(linear(v) for v in original) + (1,)
    shader.inputs["Roughness"].default_value = .54
    if tag.startswith("fresco"):
        for tex in (n for n in tree.nodes if n.type == "TEX_IMAGE"):
            tex.extension = "EXTEND"
        shader.inputs["Roughness"].default_value = .76
        shader.inputs["Specular IOR Level"].default_value = .2
        return
    if tag == "glass":
        out = next(n for n in tree.nodes if n.type == "OUTPUT_MATERIAL")
        trans = tree.nodes.new("ShaderNodeBsdfTransparent")
        gloss = tree.nodes.new("ShaderNodeBsdfGlossy")
        gloss.inputs["Roughness"].default_value = .045
        mixt = tree.nodes.new("ShaderNodeMixShader")
        mixt.inputs[0].default_value = .035
        tree.links.new(trans.outputs[0], mixt.inputs[1])
        tree.links.new(gloss.outputs[0], mixt.inputs[2])
        tree.links.new(mixt.outputs[0],out.inputs["Surface"])
        return
    if tag == "gold":
        base.default_value = (.70,.43,.14,1)
        shader.inputs["Metallic"].default_value = .93
        shader.inputs["Roughness"].default_value = .33
    scale = 350 if tag == "gold" else 210
    strength = .12 if tag == "gold" else .2
    distance = .0003 if tag == "gold" else .00055
    coord = tree.nodes.new("ShaderNodeTexCoord")
    noise = tree.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = 2.
    tree.links.new(coord.outputs["Object"],noise.inputs["Vector"])
    bump = tree.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = distance
    tree.links.new(noise.outputs["Fac"],bump.inputs["Height"])
    tree.links.new(bump.outputs["Normal"],shader.inputs["Normal"])
    if tag == "gold":
        remap = tree.nodes.new("ShaderNodeMapRange")
        remap.inputs["To Min"].default_value = .25
        remap.inputs["To Max"].default_value = .44
        tree.links.new(noise.outputs["Fac"], remap.inputs["Value"])
        tree.links.new(remap.outputs["Result"], shader.inputs["Roughness"])
    if tag in ("oak","walnut","wood"):
        mapping = tree.nodes.new("ShaderNodeVectorMath")
        mapping.operation = "MULTIPLY"
        mapping.inputs[1].default_value = (2,24,28)
        tree.links.new(coord.outputs["Object"],mapping.inputs[0])
        tree.links.new(mapping.outputs[0],noise.inputs["Vector"])
        noise.inputs["Scale"].default_value = 3
        noise.inputs["Distortion"].default_value = 1.5
        ramp = tree.nodes.new("ShaderNodeValToRGB")
        rgb = tuple(base.default_value)[:3]
        ramp.color_ramp.elements[0].color = tuple(v*.65 for v in rgb)+(1,)
        ramp.color_ramp.elements[1].color = tuple(min(v*1.48,1.) for v in rgb)+(1,)
        tree.links.new(noise.outputs["Fac"],ramp.inputs[0])
        tree.links.new(ramp.outputs["Color"],base)
        shader.inputs["Roughness"].default_value = .36
        bump.inputs["Strength"].default_value = .09


for material in bpy.data.materials:
    finish_material(material)
world = bpy.data.worlds.new("Diffuse daylight")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (.91,.94,1,1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = .32
scene.world = world


def light(name, pos, target, watts, width, source_height, color):
    lightdata = bpy.data.lights.new(name,"AREA")
    lightdata.shape = "RECTANGLE"
    lightdata.energy = watts
    lightdata.size = width
    lightdata.size_y = source_height
    lightdata.color = color
    obj = bpy.data.objects.new(name,lightdata)
    scene.collection.objects.link(obj)
    obj.location = pos
    point_at(obj,target)


glazing = [bounds(obj) for obj in meshes if any(
    slot.material and tag_name(slot.material.name) == "glass" for slot in obj.material_slots)]
for index, (lo, hi) in enumerate(glazing, 1):
    x, y, z = ((a + b) / 2 for a, b in zip(lo, hi))
    aperture, opening_height = hi[0] - lo[0], hi[2] - lo[2]
    # Place a soft emitter immediately outside each actual opening.
    light("Daylight · " + str(index), (x, y-.1, z), (x, cy, z+.32),
          52*aperture*opening_height, max(.22, aperture*.96), opening_height*.92, (.93,.95,1.))
light("Warm indirect return", position(.39,.16,.51), position(-.30,-.17,.73),
      (45 if options.editorial else 72)*length*width/60, width*.37, height*.27, (1,.865,.70))
sun_data = bpy.data.lights.new("Late daylight", "SUN")
sun_data.color = (1,.872,.73)
sun_data.energy = 2.21 if options.editorial else 1.60
sun_data.angle = .034 if options.editorial else .085
sun = bpy.data.objects.new("Late daylight",sun_data)
scene.collection.objects.link(sun)
sun.location = position(.56,-1.3,1.48)
point_at(sun,position(.1,0,.34))
camera_data = bpy.data.cameras.new("Interior lens")
camera = bpy.data.objects.new("Interior",camera_data)
scene.collection.objects.link(camera)
scene.camera = camera
side = 1 if options.opposite else -1
if options.ceiling:
    camera.location=position(0,0,.20)
    camera.rotation_euler=(math.pi,0,0)
    camera_data.type="ORTHO"
    camera_data.ortho_scale=max(length,width/.691)*1.04
elif options.detail:
    camera.location = position(.27,side*.32,.43)
    point_at(camera,position(-.23,-side*.33,.965))
    camera_data.lens = 26
    camera_data.shift_y = .02
else:
    camera.location = position(.402,side*.405,.29 if options.editorial else .33)
    point_at(camera,position(-.40,-side*.13,.54 if options.editorial else .49))
    camera_data.lens = 21 if options.editorial else 20
    camera_data.shift_y = .082 if options.editorial else .122
camera_data.clip_start = .04
scene.render.engine = "CYCLES"
scene.cycles.samples = options.samples or (12 if quick else 104)
scene.cycles.use_denoising = True
scene.cycles.adaptive_threshold = .04 if quick else .015
scene.cycles.max_bounces = 12 if options.editorial else 8
scene.cycles.diffuse_bounces = 7 if options.editorial else 5
scene.cycles.glossy_bounces = 4
scene.cycles.transparent_max_bounces = 8
addon = bpy.context.preferences.addons.get("cycles")
if addon and not options.cpu:
    for backend in ("OPTIX","CUDA"):
        try:
            prefs = addon.preferences
            prefs.compute_device_type = backend
            prefs.refresh_devices()
            candidates = [d for d in prefs.devices if d.type == backend]
            if candidates:
                for d in prefs.devices:
                    d.use = d.type == backend
                scene.cycles.device = "GPU"
                break
        except RuntimeError:
            pass
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium High Contrast"
scene.view_settings.exposure = -.19 if options.editorial else -.12
scene.render.resolution_x = options.width or (754 if quick else 1840)
scene.render.resolution_y = round(scene.render.resolution_x * 1272 / 1840)
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
output.parent.mkdir(parents=True, exist_ok=True)
scene.render.filepath = str(output)
print(f"PALACE {length:.2f} x {width:.2f} x {height:.2f} m, {len(glazing)} windows, "
      f"{len(meshes)} meshes, {scene.cycles.device}, {output}", flush=True)
bpy.ops.render.render(write_still=True)
