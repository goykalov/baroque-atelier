"""Export the same palace as Grasshopper using only Python's standard library."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile

from palace_plan import PALACE_PROFILES, _palace_compile, default_plan, generate_best
from palace_auto import new_ultra_plan
from palace_art import palace_art_paths, palace_uv
from palace_search import architecture_checked, edit_hall_zone, hall_history_item, portal_checked, search_hall, validate_hall_layout
from palace_refinement import refinement_checked
from palace_ensemble import ensemble_checked
from palace_carving import carving_fraction
from palace_room import ROOM_PALETTES, build_palace, palace_palette


def _triangulate(indices, vertices):
    """Ear-clip OBJ n-gons after projection onto the dominant plane."""
    if len(indices) == 3:
        return [tuple(indices)]
    points = [vertices[i] for i in indices]
    normal = [0., 0., 0.]
    for i, a in enumerate(points):
        b = points[(i+1) % len(points)]
        for j in range(3):
            k, l = (j+1) % 3, (j+2) % 3
            normal[j] += (a[k]-b[k]) * (a[l]+b[l])
    drop = max(range(3), key=lambda i: abs(normal[i]))
    axes = ((drop+1) % 3, (drop+2) % 3)
    xy = [(p[axes[0]], p[axes[1]]) for p in points]
    size = max(max(p[j] for p in xy) - min(p[j] for p in xy) for j in (0, 1))
    epsilon = size*size*1e-13
    if abs(normal[drop]) <= epsilon:
        raise ValueError("В OBJ есть вырожденный или самопересекающийся многоугольник")
    orientation = 1 if normal[drop] > 0 else -1

    def cross(a, b, c):
        p, q, r = xy[a], xy[b], xy[c]
        return orientation*((q[0]-p[0])*(r[1]-p[1]) - (q[1]-p[1])*(r[0]-p[0]))

    rest, triangles = list(range(len(indices))), []
    while len(rest) > 3:
        for k, b in enumerate(rest):
            a, c = rest[k-1], rest[(k+1) % len(rest)]
            if cross(a,b,c) <= epsilon:
                continue
            inside = any(min(cross(a,b,p),cross(b,c,p),cross(c,a,p)) >= -epsilon
                         for p in rest if p not in (a,b,c))
            if not inside:
                triangles.append((indices[a],indices[b],indices[c]))
                rest.pop(k)
                break
        else:
            raise ValueError("Не удалось разбить грань OBJ. Сохраните скан с триангуляцией.")
    triangles.append(tuple(indices[k] for k in rest))
    return triangles


def read_window_asset(path):
    vertices, triangles = [], []
    with path.open(encoding="utf-8-sig", errors="replace") as file:
        continuation = ""
        for line_no, line in enumerate(file, 1):
            line = continuation + line.split("#",1)[0].rstrip()
            if line.endswith(chr(92)):
                continuation = line[:-1] + " "
                continue
            continuation = ""
            words = line.split()
            if not words:
                continue
            try:
                if words[0] == "v":
                    pt = tuple(float(v) for v in words[1:4])
                    if len(pt) != 3 or not all(math.isfinite(v) for v in pt):
                        raise ValueError("Координаты вершины должны быть тремя конечными числами")
                    vertices.append(pt)
                elif words[0] == "f":
                    raw = [int(token.split("/",1)[0]) for token in words[1:]]
                    if any(i == 0 or i < -len(vertices) or i > len(vertices) for i in raw):
                        raise ValueError("Грань содержит несуществующую вершину")
                    indices = [i-1 if i>0 else len(vertices)+i for i in raw]
                    if len(indices)>3 and indices[0] == indices[-1]:
                        indices.pop()
                    if len(indices) < 3 or len(set(indices)) != len(indices):
                        raise ValueError("В грани нужны как минимум три различные вершины")
                    triangles.extend(_triangulate(indices,vertices))
            except (IndexError,ValueError) as exc:
                raise ValueError(f"{path.name}, строка {line_no}. {exc}") from exc
    if not triangles:
        raise ValueError("В скане OBJ нет полигональных граней")
    used = sorted({i for face in triangles for i in face})
    remap = {old:new for new,old in enumerate(used)}
    vertices = [vertices[i] for i in used]
    triangles = [tuple(remap[i] for i in f) for f in triangles]
    lo = [min(p[j] for p in vertices) for j in range(3)]
    hi = [max(p[j] for p in vertices) for j in range(3)]
    width, height = hi[0]-lo[0], hi[1]-lo[1]
    if min(width,height) <= 0:
        raise ValueError("Разверните наличник на плоскость XY, рельефом в сторону +Z")
    center_x, center_y = (hi[0]+lo[0])/2, (hi[1]+lo[1])/2
    normalized = [(x-center_x, y-center_y, z-lo[2]) for x,y,z in vertices]
    return normalized, triangles, width, height


def place_window_asset(room, asset, material):
    vertices, triangles, source_w, source_h = asset
    for i, (frame, width, height) in enumerate(room.windows, 1):
        factor = 1.15 * min(width/source_w, height/source_h)
        placed = [frame(x*factor,y*factor,z*factor) for x,y,z in vertices]
        room.mesh(material, f"Оконный наличник {i}", placed, triangles)


def write_obj(path, room, material_file):
    total_v, total_f, total_uv = 0, 0, 0
    with path.open("w",encoding="utf-8",newline="\n",buffering=1024*1024) as file:
        file.write("# Palace room | metres | Z up\nmtllib " + material_file + "\n")
        for (zone,mat),(v,f) in room.parts.items():
            if not f:
                continue
            name = zone.replace(" ","_")
            smoothing = "off" if mat in ("body","wood","oak","walnut","glass") else "1"
            file.write(f"o {name}__{mat}\ng {name}\nusemtl {mat}\ns {smoothing}\n")
            file.writelines("v %.7f %.7f %.7f\n" % (v[i]*.001,v[i+1]*.001,v[i+2]*.001)
                            for i in range(0,len(v),3))
            first = total_v+1
            if mat.startswith("fresco"):
                min_x,max_x=min(v[0::3]),max(v[0::3])
                min_y,max_y=min(v[1::3]),max(v[1::3])
                w,h=max(max_x-min_x,1.e-9),max(max_y-min_y,1.e-9)
                file.writelines("vt %.7f %.7f\n" % palace_uv(mat,(v[i]-min_x)/w,(max_y-v[i+1])/h,w,h)
                                for i in range(0,len(v),3))
                uv=total_uv+1
                file.writelines("f %d/%d %d/%d %d/%d\n" %
                                (f[i]+first,f[i]+uv,f[i+1]+first,f[i+1]+uv,f[i+2]+first,f[i+2]+uv)
                                for i in range(0,len(f),3))
                total_uv+=len(v)//3
            else:
                file.writelines("f %d %d %d\n" % (f[i]+first,f[i+1]+first,f[i+2]+first)
                                for i in range(0,len(f),3))
            total_v += len(v)//3
            total_f += len(f)//3
    return total_v,total_f


def write_materials(path, palette, painting=None):
    textures=painting if isinstance(painting,dict) else {"fresco":painting} if painting else {}
    materials=dict(palette)
    materials.update({k:palette["fresco"] for k in textures})
    with path.open("w", encoding="utf-8",newline="\n") as file:
        for name,rgb in materials.items():
            kd = tuple(v / 255 for v in rgb)
            if name in textures:
                kd=(1.,1.,1.)
            gloss = .64 if name=="gold" else (.28 if name=="glass" else .13)
            exponent = 104 if name=="gold" else (62 if name=="glass" else 20)
            file.write(f"newmtl {name}\nKd %.5f %.5f %.5f\n" % kd)
            file.write(f"Ks {gloss} {gloss} {gloss}\nNs {exponent}\nillum 2\n")
            if name in textures:
                file.write("map_Kd "+textures[name]+"\n")
            file.write("\n")


def _painting_source(path, src, saved_name):
    package=Path(__file__).resolve().parent
    candidates=[package/"fresco.jpg",package.parent/"fresco.jpg",path.parent/"fresco.jpg"]
    if src and saved_name:
        candidates.insert(0,src.parent/Path(saved_name).name)
    for candidate in candidates:
        if candidate.is_file():
            with candidate.open("rb") as sample:
                if sample.read(3)==bytes((255,216,255)):
                    return candidate
    return None


def read_recipe(path):
    return _recipe_from_json(json.loads(path.read_text(encoding="utf-8-sig")))


def _recipe_from_json(plan, allow_zones=True):
    rebuilt = _palace_compile(plan["program"],plan["style"],plan["seed"],plan["source"])
    for k in ("model","prompt","seconds","attempts","export","selection","interpretation","repairs","ultra","dense","input_seed","search","pattern","paintings","zone_edit"):
        if k in plan:
            rebuilt[k] = plan[k]
    if "zone_tuning" in plan:
        rebuilt["zone_tuning"] = {
            zone: {key:_range(plan["zone_tuning"][zone][key],0.,1.,key)
                   for key in ("curl","foliage","gilding")}
            for zone in ("wall","ceiling")
        }
    if rebuilt["style"] not in PALACE_PROFILES:
        raise ValueError("Неизвестный регион в рецепте")
    rebuilt["title"]=str(plan.get("title",rebuilt["title"]))[:120]
    if "architecture" in plan:
        rebuilt["architecture"]=architecture_checked(plan["architecture"])
        rebuilt["layout"]=validate_hall_layout(plan["layout"])
        if not set(rebuilt.get("paintings",{}))<={p["id"] for p in rebuilt["layout"]}:
            raise ValueError("Роспись ссылается на отсутствующее поле")
    if "refinement" in plan:
        rebuilt["refinement"]=refinement_checked(plan["refinement"],"hall" if allow_zones else "ceiling")
    if "ensemble" in plan:
        rebuilt["ensemble"]=ensemble_checked(plan["ensemble"])
    if "zones" in plan:
        zones=plan["zones"]
        if not allow_zones or not isinstance(zones,dict) or set(zones)-{"ceiling","portal"}:
            raise ValueError("Некорректные зоны рецепта")
        rebuilt["zones"]={}
        if "ceiling" in zones:
            ceiling=_recipe_from_json(zones["ceiling"],allow_zones=False)
            if not ceiling.get("architecture") or ceiling["style"]!=rebuilt["style"]:
                raise ValueError("Локальная правка потолка должна использовать материалы зала")
            rebuilt["zones"]["ceiling"]=ceiling
        if "portal" in zones:
            rebuilt["zones"]["portal"]=portal_checked(zones["portal"])
    return rebuilt


def _commit(staging, outputs):
    backups, installed = {}, []
    if any(path.exists() and not path.is_file() for path in outputs):
        raise ValueError("Выходное имя уже занято папкой. Выберите другое имя комнаты.")
    try:
        for target in outputs:
            if target.exists():
                saved = staging/(target.name+".original")
                os.replace(target,saved)
                backups[target] = saved
            os.replace(staging/target.name,target)
            installed.append(target)
    except OSError:
        for target in reversed(installed):
            target.unlink(missing_ok=True)
        for target,saved in backups.items():
            os.replace(saved,target)
        raise


def _range(value, lo, hi, name):
    if not math.isfinite(value) or not lo <= value <= hi:
        raise ValueError(f"{name} должен быть в диапазоне {lo}–{hi}")
    return value


def export(args, progress=None):
    progress = progress or (lambda message: None)
    src = args.recipe.resolve() if args.recipe else None
    obj=args.out.resolve()
    plan = read_recipe(src) if src else None
    settings = plan.get("export",{}) if plan else {}
    budget=getattr(args,"budget",None)
    ensemble_seconds=getattr(args,"ensemble_seconds",None)
    if ensemble_seconds is not None and budget is None:
        budget=3600
    scope=getattr(args,"scope","hall")
    scoped=scope!="hall"
    if ensemble_seconds is not None and scoped:
        raise ValueError("Объёмная композиция запускается для целого зала")
    if scoped:
        if plan is None or not args.prompt or not budget:
            raise ValueError("Для правки зоны откройте рецепт, введите запрос и задайте время поиска")
        args=argparse.Namespace(**vars(args))
        for field in ("size","detail","relief","foliage","gilding","window_scan","window_material","painting","style"):
            setattr(args,field,None)
        args.no_scan=False
    requested_carving = None if scoped else getattr(args,"carving_pct",None)
    carving_pct = settings.get("carving_pct") if requested_carving is None else requested_carving
    if not scoped and getattr(args,"classic_carving",False):
        carving_pct = None
    carving_fraction(carving_pct)
    dense=getattr(args,"dense",False) or bool(budget)
    ultra=getattr(args,"ultra",False) or dense
    style = args.style or (plan["style"] if plan else "random" if ultra else "bavarian")
    seed = args.seed if args.seed is not None else (plan["seed"] if plan else 1)
    checkpoint_path=obj.with_suffix(".checkpoint.json")
    checkpoint_written=False
    def checkpoint(candidate):
        nonlocal checkpoint_written
        saved=dict(candidate,export=dict(settings,
            size_m=tuple(args.size or settings.get("size_m",(12,8.5,6.8))),
            detail=args.detail if args.detail is not None else settings.get("detail",3),
            relief=args.relief if args.relief is not None else settings.get("relief",1.3),
            foliage_delta=args.foliage if args.foliage is not None else settings.get("foliage_delta",0),
            gilding_delta=args.gilding if args.gilding is not None else settings.get("gilding_delta",0),
            carving_pct=carving_pct,
            painting=args.painting if getattr(args,"painting",None) is not None else settings.get("painting",True)))
        if scoped and src.parent!=obj.parent and settings.get("window_scan"):
            scan=(src.parent/settings["window_scan"]).resolve()
            saved["export"]["window_scan"]=str(scan)
        obj.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile("w",encoding="utf8",dir=obj.parent,prefix=".palace-checkpoint-",delete=False) as file:
            temporary=Path(file.name)
            json.dump(saved,file,ensure_ascii=False,indent=2)
        try:
            os.replace(temporary,checkpoint_path)
            checkpoint_written=True
        finally:
            temporary.unlink(missing_ok=True)
    if scoped:
        plan=edit_hall_zone(plan,scope,args.prompt,seed=args.seed,budget=budget,progress=progress,backend=args.backend,
                            size_m=tuple(settings.get("size_m",(12,8.5,6.8))),
                            finish=getattr(args,"finish",None),checkpoint=checkpoint)
    elif budget and (not plan or args.prompt):
        history=[]
        if src is None:
            candidates=list(obj.parent.glob("*.recipe.json"))
            for r in sorted(candidates,key=lambda x:x.stat().st_mtime)[-12:]:
                try:
                    candidate=read_recipe(r)
                    if candidate.get("architecture"):
                        history.append(hall_history_item(candidate))
                except (ValueError,KeyError,TypeError,OSError):
                    continue
            avoid_path=getattr(args,"avoid",None)
            if avoid_path and avoid_path.is_file():
                candidate=hall_history_item(read_recipe(avoid_path))
                if candidate not in history:history.append(candidate)
        targeted_size=tuple(args.size or settings.get("size_m",(12,8.5,6.8)))
        plan=search_hall(args.prompt,style,args.seed,plan,budget,history,progress,args.backend,targeted_size,
                         finish=getattr(args,"finish",None),checkpoint=checkpoint,
                         ensemble_seconds=ensemble_seconds)
        style=plan["style"]
    elif ultra and (not plan or args.prompt):
        progress("Локальный подбор композиции")
        avoid_path=getattr(args,"avoid",None)
        avoid=read_recipe(avoid_path) if avoid_path and avoid_path.is_file() else None
        plan=new_ultra_plan(args.prompt,style,args.seed,plan,args.backend,args.drafts,avoid,dense=dense)
        style=plan["style"]
    elif args.prompt:
        backend, attempts = getattr(args,"backend","rules"), getattr(args,"drafts",3)
        progress("Подбор композиций · " + str(attempts))
        plan = generate_best(args.prompt,style,seed,plan,attempts=attempts,backend=backend)
    elif plan is None:
        plan = default_plan(style,seed)
    elif style != plan["style"] or seed != plan["seed"]:
        raise ValueError("Чтобы изменить стиль или seed готового рецепта, передайте также --prompt для новой редакции")
    default_size=(12,8.5,6.8) if plan.get("dense") else (9,6.7,4.9)
    size = tuple(args.size or settings.get("size_m",default_size))
    detail = args.detail if args.detail is not None else settings.get("detail",3 if ultra else 2)
    depth = args.relief if args.relief is not None else settings.get("relief",1.3 if ultra else 1)
    foliage = args.foliage if args.foliage is not None else settings.get("foliage_delta",0)
    gold = args.gilding if args.gilding is not None else settings.get("gilding_delta",0)
    if len(size)!=3 or not all(math.isfinite(v) for v in size):
        raise ValueError("Нужны три размера комнаты в метрах")
    _range(detail,1,3,"Уровень детализации")
    _range(depth,.35,2,"Рельеф")
    _range(foliage,-1,1,"Сдвиг густоты листвы")
    _range(gold,-1,1,"Сдвиг позолоты")
    scan = args.window_scan
    if scan is None and src and settings.get("window_scan") and not args.no_scan:
        scan = src.parent / settings["window_scan"]
    scan = scan.resolve() if scan else None
    material = args.window_material or settings.get("window_material","plaster")
    if material not in ROOM_PALETTES[style]:
        raise ValueError("В палитре отсутствует материал наличника " + str(material))
    paint_setting=getattr(args,"painting",None)
    requested=settings.get("painting",True) if paint_setting is None else paint_setting
    ceiling=plan.get("zones",{}).get("ceiling",plan)
    art=_painting_source(obj,src,settings.get("painting_texture")) if requested and ceiling.get("ultra",{}).get("paint",True) else None
    picked_art=palace_art_paths(plan,Path(__file__).resolve().parent) if requested and "paintings" in plan else {}
    painting_geom=(ceiling["paintings"] if requested else {}) if "paintings" in ceiling else bool(art)
    progress("Построение комнаты и объёмной лепнины")
    asset = read_window_asset(scan) if scan else None
    room = build_palace(plan,tuple(v*1000 for v in size),detail,depth,foliage,gold,
                        window_asset=bool(asset),painting=painting_geom,carving_pct=carving_pct)
    if asset:
        place_window_asset(room,asset,material)
    if obj.suffix.lower() != ".obj":
        raise ValueError("Имя выходного файла должно заканчиваться .obj")
    obj.parent.mkdir(parents=True,exist_ok=True)
    mtl,recipe = obj.with_suffix(".mtl"),obj.with_suffix(".recipe.json")
    if scan in (obj,mtl,recipe):
        raise ValueError("Выберите разные файлы для входного скана и выходной комнаты")
    scan_ref = None
    if scan:
        try:
            scan_ref = os.path.relpath(scan,recipe.parent)
        except ValueError:
            scan_ref = str(scan)
    with tempfile.TemporaryDirectory(prefix=".palace-",dir=obj.parent) as directory:
        staging = Path(directory)
        progress("Запись геометрии, материалов и рецепта")
        counts = write_obj(staging/obj.name,room,mtl.name)
        outputs=[mtl,recipe,obj]
        texture=None
        if art and any(mat=="fresco" for zone,mat in room.parts):
            texture=obj.parent/"fresco.jpg"
            if texture.exists() and art.resolve()!=texture.resolve():
                digest=hashlib.sha256(art.read_bytes()).hexdigest()
                if digest!=hashlib.sha256(texture.read_bytes()).hexdigest():
                    texture=obj.parent/("fresco-"+digest[:12]+".jpg")
            if not texture.exists():
                shutil.copyfile(art,staging/texture.name)
                outputs.insert(0,texture)
        maps={"fresco":texture.name} if texture else {}
        for key,asset_path in picked_art.items():
            if not any(mat==key for zone,mat in room.parts):continue
            target=obj.parent/("baroque-"+key+".jpg")
            if target==asset_path or target.is_file() and hashlib.sha256(target.read_bytes()).digest()==hashlib.sha256(asset_path.read_bytes()).digest():
                maps[key]=target.name
                continue
            shutil.copyfile(asset_path,staging/target.name)
            outputs.insert(0,target)
            maps[key]=target.name
        write_materials(staging/mtl.name,palace_palette(style,carving_pct is not None),maps)
        saved = dict(plan,export=dict(size_m=size,detail=detail,relief=depth,
                    foliage_delta=foliage,gilding_delta=gold,carving_pct=carving_pct,window_scan=scan_ref,
                    window_material=material,window_instances=len(room.windows),painting=bool(requested),
                    painting_texture=texture.name if texture else None,
                    painting_textures=maps,
                    vertices=counts[0],triangles=counts[1]))
        if carving_pct is not None:
            saved["export"]["carved_pieces"]=room.carved_pieces
        (staging/recipe.name).write_text(json.dumps(saved,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        _commit(staging,outputs)
    if checkpoint_written:
        checkpoint_path.unlink(missing_ok=True)
    return obj,counts


def main():
    parser=argparse.ArgumentParser(description="Создать редактируемую полигональную барочную комнату. Python 3.9+.")
    parser.add_argument("--out",type=Path,default=Path("room.obj"),help="Путь к OBJ. Рядом сохраняются MTL и JSON.")
    parser.add_argument("--recipe",type=Path,help="Сохранённый рецепт комнаты в JSON.")
    parser.add_argument("--prompt",help="Описание комнаты или правка проекта с --recipe.")
    parser.add_argument("--ensemble-seconds",type=int,
                        help="Включить поиск объёмной композиции и выделить ему указанное число секунд.")
    parser.add_argument("--scope",choices=("hall","ceiling","portal"),default="hall",
                        help="При правке рецепта ограничивает изменения потолком или лепниной над дверью.")
    parser.add_argument("--backend",choices=("rules","native"),default="rules",
                        help="rules — автономные правила, native — локальный запуск llama.cpp.")
    parser.add_argument("--drafts",type=int,choices=(1,2,3,4),default=3,help="Число быстрых схем для отбора по одному запросу.")
    parser.add_argument("--style",choices=(*PALACE_PROFILES,"random"),help="Художественный профиль. random выбирает школу автоматически.")
    parser.add_argument("--ultra",action="store_true",help="Собрать новый пышный зал. Пустое задание создаёт случайную композицию.")
    parser.add_argument("--dense",action="store_true",help="Собрать зал с многоярусным ветвящимся рельефом.")
    parser.add_argument("--budget",type=int,choices=(60,600,3600),help="Запустить композиционный поиск с бюджетом в секундах.")
    parser.add_argument("--avoid",type=Path,help="Рецепт предыдущего зала для сравнения при новом случайном запуске.")
    parser.add_argument("--seed",type=int,help="Число для воспроизводимого варианта.")
    parser.add_argument("--size",metavar=("ДЛИНА","ШИРИНА","ВЫСОТА"),nargs=3,type=float,help="Внутренние размеры в метрах.")
    parser.add_argument("--detail",type=int,choices=(1,2,3),help="1 — эскиз, 2 — обычный, 3 — тонкая резьба.")
    parser.add_argument("--relief",type=float,help="Коэффициент глубины 0.35–2.")
    parser.add_argument("--foliage",type=float,help="Поправка количества листвы от -1 до 1.")
    parser.add_argument("--gilding",type=float,help="Поправка позолоты от -1 до 1.")
    carving=parser.add_mutually_exclusive_group()
    carving.add_argument("--carving",dest="carving_pct",type=float,
                         help="Резной зал с влиянием формулы 0–100 %.")
    carving.add_argument("--classic-carving",action="store_true",help="Прежняя геометрия лепнины.")
    group=parser.add_mutually_exclusive_group()
    group.add_argument("--no-paint",dest="painting",action="store_false",help="Лепной мотив вместо живописи на центральном поле.")
    group.add_argument("--paint",dest="painting",action="store_true",help="Роспись центрального поля из комплектного fresco.jpg.")
    parser.set_defaults(painting=None)
    group=parser.add_mutually_exclusive_group()
    group.add_argument("--window-scan",type=Path,help="Скан наличника в OBJ. Вид спереди в плоскости XY, рельеф к +Z.")
    group.add_argument("--no-scan",action="store_true",help="Использовать встроенный наличник для сохранённого рецепта.")
    parser.add_argument("--window-material",choices=("gold","plaster","accent","wood","shadow","ground"),
                        help="Материал пользовательского наличника.")
    try:
        out,(verts,faces)=export(parser.parse_args())
    except (ValueError,KeyError,OSError,TypeError,RuntimeError) as err:
        parser.exit(2,f"Ошибка: {err}\n")
    print(f"{out}\nВершин {verts:,}, треугольников {faces:,}.")


if __name__ == "__main__":
    main()
