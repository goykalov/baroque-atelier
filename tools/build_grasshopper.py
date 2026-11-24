#! python 3
import base64
import json
import os
import time
import traceback

import clr
import Grasshopper as gh
import Rhino
import Rhino.Geometry as G
import scriptcontext as sc
import System
from System.Drawing import Color, PointF, RectangleF
from System.Windows.Forms import MouseButtons, MouseEventArgs, Timer
from Grasshopper.Kernel.Parameters import Param_Brep, Param_Mesh
from Grasshopper.Kernel.Special import GH_BooleanToggle, GH_ButtonObject, GH_Group, GH_Panel, GH_ValueList, GH_ValueListItem


tool_dir = os.path.dirname(os.path.abspath(__file__))
root = os.path.join(os.path.dirname(tool_dir), "atelier")
path = os.path.join(root, "Atelier.gh")
report = {}


def source(name):
    with open(os.path.join(root, name), encoding="utf8") as file:
        return file.read()


with open(os.path.join(tool_dir, "bq_factory.py"), encoding="utf8") as file:
    exec(file.read())

def build():
    clr.AddReference("GH_IO")
    import GH_IO
    rd = Rhino.RhinoDoc.ActiveDoc
    doc = gh.Kernel.GH_Document()

    def add(obj, label, x, y):
        obj.NickName = label
        obj.CreateAttributes()
        obj.Attributes.Pivot = PointF(x, y)
        doc.AddObject(obj, False)
        return obj

    def panel(label, text, x, y, width, height, src=None):
        obj = add(GH_Panel(), label, x, y)
        obj.MultilineData = True
        obj.UserText = text
        obj.Attributes.Bounds = RectangleF(x, y, width, height)
        if src is not None:
            obj.AddSource(src)
        return obj

    def menu(label, pairs, x, y):
        obj = add(GH_ValueList(), label, x, y)
        obj.ListItems.Clear()
        for name, key in pairs:
            obj.ListItems.Add(GH_ValueListItem(name, '"' + key + '"'))
        obj.SelectItem(0)
        return obj

    def group(label, color, *objects):
        obj = GH_Group()
        obj.NickName = label
        obj.Colour = Color.FromArgb(68, *color)
        for member in objects:
            obj.AddObject(member.InstanceGuid)
        doc.AddObject(obj, False)

    schools = [("Случайная школа", "random"), ("Баварское придворное рококо", "bavarian"),
               ("Елизаветинское барокко", "russian"), ("Новоиспанское барокко", "mexican")]
    prompt = panel("Задание (можно оставить пустым)", "", 55, 55, 410, 92)
    school = menu("Школа", schools, 55, 184)
    backend = menu("Режим", [("Qwen без сети", "native"), ("Автономные правила", "rules")], 55, 232)
    trials = menu("Время поиска", [("До 1 минуты","60"),("До 10 минут","600"),("До 1 часа","3600")],55,278)
    fresh = add(GH_ButtonObject(), "Найти новый зал", 55, 328)
    group("Ателье барокко   ·   задание необязательно", (182, 134, 69), prompt, school, backend, trials, fresh)

    script = source("palace_plan.py").replace(
        "base = Path(__file__).resolve().parent",
        "base = Path(ghenv.Component.OnPingDocument().FilePath).resolve().parent",
    )
    planning = "\n".join(("_PALACE_ARCHITECTURE_RELEASE=True", script,
                          source("palace_auto.py"), source("palace_architecture.py"),
                          source("palace_art.py"), source("palace_search.py"),
                          source("palace_controller.py")))
    author = python_node(doc, "Композиция зала", planning,
                          list(zip(("prompt","style","backend","trials","fresh","plan_length","plan_width","plan_height"),
                                   (prompt,school,backend,trials,fresh,None,None,None))), "status", 637, 162, True)
    panel("Генерация", "", 834, 127, 365, 66, author.Params.Output[0])
    archive = panel("Рецепт текущего зала", json.dumps({"plan": None}), 55, 790, 350, 58)

    items = [("archive", archive)]
    sliders = [
        ("length_mm","Длина зала, мм",12000,3400,18000), ("width_mm","Ширина зала, мм",8500,3400,18000),
        ("height_mm","Высота зала, мм",6800,2700,8000), ("detail","Детализация",3,1,3),
        ("depth","Высота рельефа, %",115,35,200), ("leaves","Поправка густоты листвы, %",0,-100,100),
        ("gold","Поправка позолоты, %",0,-100,100),
    ]
    for i, (key, label, value, lo, hi) in enumerate(sliders):
        items.append((key, dial(doc, label, value, lo, hi, 55+(i//4)*365, 449+(i%4)*47)))
    measurements = dict(items)
    for i,axis in enumerate(("length_mm","width_mm","height_mm"),5):
        author.Params.Input[i].AddSource(measurements[axis])
    room = add(Param_Brep(), "Объём зала", 867, 445)
    scan = add(Param_Mesh(), "Оконная резьба", 867, 492)
    room.Hidden = scan.Hidden = True
    view = add(GH_ButtonObject(), "Вид из зала", 867, 539)
    paint = add(GH_BooleanToggle(), "Живопись на потолке", 867, 586)
    paint.Value = True
    growth = dial(doc, "Разрастание ветвей, %", 100, 45, 160, 420, 591)
    levels = menu("Уровни ветвления", [("Глубина ветвления · авто", "auto"), ("3 уровня", "3"), ("4 уровня", "4")], 420, 640)
    items.extend([("room",room),("scan_input",scan),("view",view),("painting",paint),
                  ("growth_pct",growth),("branch_levels",levels)])
    group("Параметры зала и лепнины", (114, 152, 139), *[obj for _, obj in items[1:]])

    with open(os.path.join(tool_dir, "PalaceBuffers.dll"), "rb") as f:
        buffers = base64.b64encode(f.read()).decode()
    geom = "\n".join(("import json", "_PALACE_ARCHITECTURE_RELEASE=True", "PALACE_DLL=" + repr(buffers), *(source(n) for n in (
        "palace_ornament.py", "palace_branching.py", "palace_room.py", "palace_enrichment.py", "palace_sculpture.py",
        "palace_dense_walls.py", "palace_dense_ceiling.py", "palace_architecture.py", "palace_art.py", "palace_rhino.py", "palace_display.py",
    ))))
    display = python_node(doc, "Архитектура и резьба в Rhino", geom, items, "status", 687, 797, True)
    display.Hidden = True
    panel("Модель Rhino", "", 905, 764, 390, 66, display.Params.Output[0])

    if gh.Instances.ActiveCanvas is None:
        Rhino.RhinoApp.RunScript("_Grasshopper", False)
    canvas = gh.Instances.ActiveCanvas
    doc.FilePath = path
    gh.Instances.DocumentServer.AddDocument(doc)
    canvas.Document = doc
    doc.NewSolution(True)
    def status(obj):
        return "".join(str(v) for v in obj.Params.Output[0].VolatileData.AllData(True))
    report["opening"] = status(display)
    assert "Найти новый зал" in report["opening"], report["opening"]
    graph = GH_IO.Serialization.GH_Archive()
    graph.AppendObject(doc, "Definition")
    assert graph.WriteToFile(path, True, False)
    io = gh.Kernel.GH_DocumentIO()
    assert io.Open(path)
    report["reopened"] = True


build()
print("Built and reopened:",path)
