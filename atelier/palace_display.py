import hashlib
import os
import scriptcontext as sc


def geometric_input(index):
    port = ghenv.Component.Params.Input[index]
    return next((getattr(value, "Value", value) for src in port.Sources
                 for value in src.VolatileData.AllData(True) if value is not None), None)


def display_room():
    active = json.loads(str(archive)).get("plan")
    if active is None:
        return "Нажмите «Найти новый зал»" if "_PALACE_ARCHITECTURE_RELEASE" in globals() else "Нажмите «Новый ветвящийся зал»" if "growth_pct" in globals() else "Нажмите «Новый пышный зал»"
    if active.get("dense") and "growth_pct" in globals():
        options = dict(active["dense"])
        if float(growth_pct) != 100.:
            options["growth"] = max(.45, min(1.6, options["growth"]*float(growth_pct)/100))
        if str(branch_levels) in ("3","4"):
            options["order"] = int(branch_levels)
        active = dict(active, dense=options)
    rd = Rhino.RhinoDoc.ActiveDoc
    if rd is None:
        raise ValueError("Откройте документ Rhino")
    node = ghenv.Component
    owner = str(node.InstanceGuid)
    doc = node.OnPingDocument()
    size, placement = room_transform(rd, (float(length_mm), float(width_mm), float(height_mm)), geometric_input(8))
    scan = geometric_input(9)
    picture = os.path.join(os.path.dirname(doc.FilePath or ""), "fresco.jpg")
    paint_enabled=str(painting).lower()=="true"
    if "paintings" in active:
        painted=active["paintings"] if paint_enabled else {}
        textures=palace_art_paths(active,os.path.dirname(doc.FilePath or "")) if paint_enabled else {}
    else:
        painted=paint_enabled and os.path.isfile(picture)
        textures={"fresco":picture} if painted else {}
    settings = (active, size, str(placement), int(float(detail)), float(depth), float(leaves),
                float(gold), scan.DataCRC(0) if scan is not None else None,
                [(k,str(p),os.path.getmtime(p)) for k,p in textures.items()])
    stamp = hashlib.sha256(json.dumps(settings, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    key = ("palace-ultra-room", owner, rd.RuntimeSerialNumber)
    cache = sc.sticky.get(key)
    if cache is None or cache[0] != stamp:
        built = build_palace(active, size, int(float(detail)), float(depth)/100, float(leaves)/100,
                            float(gold)/100, scan is not None, painted)
        meshes = room_meshes(built, active["style"], placement, scan, textures)
        publish_palace(rd, owner, stamp, meshes, textures)
        count = sum(mesh.Faces.Count for mesh in meshes[0])
        if cache is None or cache[2] != active["seed"]:
            palace_camera(rd, size, placement)
        sc.sticky[key] = (stamp, count, active["seed"])
    if str(view).lower() == "true":
        palace_camera(rd, size, placement)
    count = sc.sticky[key][1]
    return "{} · {} полей · {:,} треугольников".format(active["title"], len(active["layout"]), count).replace(",", " ")


try:
    status = display_room()
except Exception as error:
    status = "Ошибка · " + str(error)
