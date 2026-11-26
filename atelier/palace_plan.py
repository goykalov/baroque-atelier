"""Bounded local room-composition grammar. Geometry uses normalized panel bounds."""
import json
import copy
import hashlib
import math
import os
from pathlib import Path
import random
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.request


PALACE_MODEL = "qwen3.8:27b"
PALACE_URL = "http://127.0.0.1:11434/api/chat"
PALACE_SHAPES = ("oval", "lobed", "octagon", "arch", "rect")
PALACE_MOTIFS = ("shell", "sunburst", "vine", "flower")
PALACE_ELEMENTS = ("shell", "fan", "spray", "beads", "rosette", "scroll")
PALACE_RHYTHMS = ("uniform", "alternating", "processional")
PALACE_PROFILES = {
    "bavarian": ("Баварский рокайль", "Light plaster, asymmetric rocaille shell, open cartouches, shallow gilded accents.", .80, .61, .34, "lobed", "shell", ("shell", "scroll", "spray"), "alternating", 3),
    "russian": ("Елизаветинский зал", "Palatial Elizabethan interpretation, ordered wall bays, aligned gilded frames, strong central axis, scrolls, radial or foliate crests.", .60, .70, .78, "arch", "sunburst", ("fan", "scroll", "beads"), "processional", 4),
    "mexican": ("Новоиспанская резьба", "New Spanish retablo-inspired interpretation, deep layered niches and piers, carved rosettes, clustered foliate work. Keep the main accents legible.", .72, .91, .85, "octagon", "flower", ("rosette", "spray", "beads"), "alternating", 3),
}


def _palace_obj(props):
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def _palace_list(item, lo, hi):
    return {"type": "array", "items": item, "minItems": lo, "maxItems": hi}


def _palace_enum(options):
    return {"type": "string", "enum": list(options)}


def _palace_schema():
    weight = {"type": "integer", "minimum": 1, "maximum": 8}
    fraction = {"type": "number", "minimum": 0, "maximum": 1}
    descriptor = _palace_obj({
        "shape": _palace_enum(PALACE_SHAPES), "motif": _palace_enum(PALACE_MOTIFS),
        "elements": _palace_list(_palace_enum(PALACE_ELEMENTS), 1, 4),
    })
    cell = _palace_obj({"weight": weight, "type": _palace_enum(("A", "B", "C", "void"))})
    band = _palace_obj({"weight": weight, "cells": _palace_list(cell, 1, 5)})
    return _palace_obj({
        "title": {"type": "string"}, "curl": fraction, "foliage": fraction, "gilding": fraction,
        "wall_bays": {"type": "integer", "minimum": 2, "maximum": 6},
        "wall_rhythm": _palace_enum(PALACE_RHYTHMS), "wall": descriptor,
        "palette": _palace_obj({key: descriptor for key in "ABC"}),
        "axis": _palace_enum(("x", "y")), "bands": _palace_list(band, 1, 5),
    })


def _palace_choice(value, options):
    if value not in options:
        raise ValueError("Неизвестное значение " + repr(value)[:100])
    return value


def _palace_number(value, lo, hi, integral=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lo <= value <= hi:
        raise ValueError("Число вне диапазона " + str((lo, hi)))
    if integral and value != int(value):
        raise ValueError("Нужно целое число")
    return int(value) if integral else float(value)


def _palace_descriptor(spec):
    elements = spec["elements"]
    if not isinstance(elements, list) or not 1 <= len(elements) <= 4:
        raise ValueError("В мотиве должно быть от одного до четырёх ярусов")
    return {
        "shape": _palace_choice(spec["shape"], PALACE_SHAPES),
        "motif": _palace_choice(spec["motif"], PALACE_MOTIFS),
        "elements": list(dict.fromkeys(_palace_choice(e, PALACE_ELEMENTS) for e in elements)),
    }


def _palace_spans(cells):
    if not isinstance(cells, list) or not 1 <= len(cells) <= 5:
        raise ValueError("Допустимо от одной до пяти секций")
    weights = [_palace_number(c["weight"], 1, 8, True) for c in cells]
    cursor, total = -1., sum(weights)
    for cell, weight in zip(cells, weights):
        span = weight / total
        yield cell, cursor + span, span
        cursor += 2 * span


def _palace_compile(program, style, seed, source):
    axis = _palace_choice(program["axis"], ("x", "y"))
    palette = {k: _palace_descriptor(program["palette"][k]) for k in "ABC"}
    wall = _palace_descriptor(program["wall"])
    layout = []
    for row, (band, a, da) in enumerate(_palace_spans(program["bands"])):
        for column, (cell, b, db) in enumerate(_palace_spans(band["cells"])):
            key = _palace_choice(cell["type"], ("A", "B", "C", "void"))
            if key == "void":
                continue
            x, y, rx, ry = (a, b, da, db) if axis == "x" else (b, a, db, da)
            # Leave a continuous cornice margin plus a grout strip per panel.
            x, y, rx, ry = x * .95, y * .95, rx * .92 - .012, ry * .92 - .012
            if min(rx, ry) < .075:
                raise ValueError("Слишком узкое поле " + str((row, column)) + ". Сблизьте веса секций.")
            descriptor = dict(palette[key])
            if "focal_motif" in cell:
                descriptor["motif"] = _palace_choice(cell["focal_motif"], PALACE_MOTIFS)
            layout.append(dict(descriptor, id="p%d_%d" % (row + 1, column + 1),
                               x=round(x, 6), y=round(y, 6), rx=round(rx, 6), ry=round(ry, 6)))
    if not 1 <= len(layout) <= 16:
        raise ValueError("Допустимо от одного до шестнадцати полей потолка")
    title = program["title"]
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Пустое название")
    return {
        "version": 1, "style": style, "seed": int(seed), "source": source,
        "title": title.strip()[:120], "layout": layout,
        "curl": _palace_number(program["curl"], 0, 1),
        "foliage": _palace_number(program["foliage"], 0, 1),
        "gilding": _palace_number(program["gilding"], 0, 1),
        "wall_bays": _palace_number(program["wall_bays"], 2, 6, True),
        "wall_rhythm": _palace_choice(program["wall_rhythm"], PALACE_RHYTHMS),
        "wall_shape": wall["shape"], "wall_motif": wall["motif"], "wall_elements": wall["elements"],
        "program": program,
    }


def default_plan(style, seed):
    """An immediately usable explicit procedural starter; its provenance is recorded."""
    profile = PALACE_PROFILES[_palace_choice(style, PALACE_PROFILES)]
    title, _, curl, foliage, gilding, shape, motif, elements, rhythm, bays = profile
    rng = random.Random(int(seed))
    wall = {"shape": shape, "motif": motif, "elements": list(elements)}
    palette = {"A": dict(wall), "B": {"shape": "oval", "motif": "vine", "elements": ["spray", "scroll"]},
               "C": {"shape": "lobed", "motif": "flower", "elements": ["rosette", "beads"]}}
    if style == "bavarian":
        rows = [(1, "B B"), (rng.choice((3, 4)), "A"), (1, "B B")]
    elif style == "russian":
        rows = [(2, "C"), (rng.choice((3, 4)), "A"), (2, "C")]
    else:
        rows = [(1, "B C B"), (rng.choice((2, 3)), "C A C"), (1, "B C B")]
    bands = [{"weight": w, "cells": [{"weight": 2 if t == "A" else 1, "type": t}
                                        for t in types.split()]} for w, types in rows]
    program = dict(title=title, curl=curl, foliage=foliage, gilding=gilding, wall_bays=bays,
                   wall_rhythm=rhythm, wall=wall, palette=palette, axis="x", bands=bands)
    return _palace_compile(program, style, seed, "procedural")


def _palace_expectations(prompt):
    text = prompt.lower().replace("ё", "е")
    stem = r"(?:пол(?:е|я|ей)|медальон(?:а|ов)?|кессон(?:а|ов)?)\b"
    words = "одно один два две три четыре пять шесть семь восемь девять десять"
    counts = dict(zip(words.split(), (1,1,2,2,3,4,5,6,7,8,9,10)))
    number = re.search(r"\b(\d{1,2}|" + "|".join(counts) + r")\s+(?:отдельн\w*\s+)?" + stem, text)
    count = (int(number[1]) if number[1].isdigit() else counts[number[1]]) if number else None
    empty_center = bool(re.search(r"(?:пуст\w*|свободн\w*)\s+(?:центр\w*|середин\w*)|(?:центр\w*|середин\w*)\s+(?:(?:потолка|остав\w*)\s+){0,2}(?:пуст\w*|свободн\w*)", text))
    four_corners = bool(re.search(r"(?:четыр[а-я]*|4|всех)\s+(?:(?:украшенн|декорированн)\w*\s+)?угл\w*", text))
    if _palace_clear_corners(text):
        four_corners = False
    return count, empty_center, four_corners


def _palace_clear_corners(text):
    return bool(re.search(r"(?:пуст\w*|свободн\w*|чист\w*)\s+(?:(?:четыре|все)\s+)?угл\w*|угл\w*\s+(?:(?:потолка|комнаты|зала|остав\w*|будут|должны|быть)\s+){0,3}(?:пуст\w*|свободн\w*|чист\w*)|(?:очист\w*|освободи\w*)\s+(?:все\s+)?угл\w*", text))


if "_PALACE_ARCHITECTURE_RELEASE" not in globals():
    from palace_ornament import _palace_inside


def _palace_mask(plan):
    pixels = set()
    for p in plan["layout"]:
        for i in range(max(-24, math.floor((p["x"]-p["rx"])*24)), min(24, math.ceil((p["x"]+p["rx"])*24))+1):
            for j in range(max(-24, math.floor((p["y"]-p["ry"])*24)), min(24, math.ceil((p["y"]+p["ry"])*24))+1):
                if _palace_inside(p, i/24, j/24):
                    pixels.add((i, j))
    return pixels


def _palace_check_intent(plan, prompt):
    count, empty_center, four_corners = _palace_expectations(prompt)
    panels = plan["layout"]
    if count is not None and count != len(panels):
        raise ValueError("Нужно полей: %s, получено: %s. Исправьте число непустых ячеек." % (count, len(panels)))
    pixels = _palace_mask(plan)
    if empty_center and any(max(abs(i), abs(j)) <= 4 for i, j in pixels):
        raise ValueError("The middle must be empty. Add void cells covering the central 30% square.")
    corners = {(i>0,j>0) for i,j in pixels if 16 <= min(abs(i), abs(j)) and max(abs(i),abs(j)) <= 21}
    if four_corners and len(corners) != 4:
        raise ValueError("Each of four corners must receive a nonempty panel.")
    if _palace_clear_corners(prompt.lower()) and corners:
        raise ValueError("Leave all four outer corner zones empty (void), with no panel over them.")


def _palace_focal(plan, prompt):
    patterns = [(r"солнеч\w*|лучист\w*","sunburst"),(r"раковин\w*|ракуш\w*","shell"),
                (r"виноград\w*|лоз[а-я]+","vine"),(r"цветоч\w*|цветок|цветы","flower")]
    for s in re.split(r"[.;,!?:]",prompt.lower()):
        if not re.search(r"в\s+центре|в\s+середине|центральн\w*\s+(?:пол\w*|мотив|медальон|раковин\w*|цветок|венец|розетк\w*)",s):
            continue
        if re.search(r"(?:пуст|свобод|без\s+)",s):
            continue
        motif=next((m for pat,m in patterns if re.search(pat,s)),None)
        if motif is None: continue
        center=next((p for p in plan["layout"] if _palace_inside(p,0,0)),None)
        if center is None:
            raise ValueError("Для названного центрального мотива нужно поле в центре потолка.")
        if center["motif"]!=motif:
            center["motif"]=motif
            if "_" in center["id"]:
                i,j=[int(k)-1 for k in center["id"][1:].split("_")]
                plan["program"]["bands"][i]["cells"][j]["focal_motif"]=motif
            plan.setdefault("repairs",[]).append("Указанный в запросе центральный мотив: "+motif)
        return


def _palace_native_files():
    base = Path(__file__).resolve().parent
    executables = ([Path(os.environ["BAROQUE_LLAMA_BIN"])] if os.environ.get("BAROQUE_LLAMA_BIN") else [])
    executables.extend((base/"engine"/"llama-completion.exe", base.parent/"engine"/"llama-completion.exe",
                        base/"llama-b12651-vulkan"/"llama-completion.exe"))
    engine = next((p for p in executables if p.is_file()),None)
    if engine is None: raise RuntimeError("Не найден llama-completion.exe. Укажите BAROQUE_LLAMA_BIN или поместите движок в папку engine.")
    paths = [Path(os.environ["BAROQUE_MODEL_PATH"])] if os.environ.get("BAROQUE_MODEL_PATH") else []
    paths.extend((base/"models"/"qwen3-8b.gguf", base.parent/"models"/"qwen3-8b.gguf"))
    if not paths[0].is_file():
        model_root = Path(os.environ.get("OLLAMA_MODELS", Path.home()/".ollama"/"models"))
        manifest = model_root/"manifests"/"registry.ollama.ai"/"library"/"qwen3"/"8b"
        if manifest.is_file():
            for layer in json.loads(manifest.read_text(encoding="utf-8"))["layers"]:
                if layer["mediaType"]=="application/vnd.ollama.image.model" and re.fullmatch(r"sha256:[0-9a-f]{64}",layer["digest"]):
                    paths.append(model_root/"blobs"/layer["digest"].replace(":","-"))
    model = next((p for p in paths if p.is_file()),None)
    if model is None: raise RuntimeError("Не найден локальный файл Qwen3:8b GGUF. Укажите BAROQUE_MODEL_PATH.")
    with model.open("rb") as f:
        if f.read(4)!=b"GGUF": raise ValueError("Нужен локальный файл модели формата GGUF")
    return engine, model


def _palace_native_response(messages, schema, seed, temperature):
    engine, model = _palace_native_files()
    parts=["<|im_start|>"+m["role"]+"\n"+m["content"]+"<|im_end|>" for m in messages]
    # Qwen3 chat template with thinking disabled. Grammar applies to generated text only.
    parts.append("<|im_start|>assistant\n<think>\n\n</think>\n\n")
    with tempfile.TemporaryDirectory(prefix="baroque-llama-") as tmp:
        prompt_path, schema_path=Path(tmp)/"prompt.txt",Path(tmp)/"schema.json"
        prompt_path.write_text("\n".join(parts),encoding="utf-8")
        schema_path.write_text(json.dumps(schema,ensure_ascii=False),encoding="utf-8")
        cmd=[str(engine),"-m",str(model),"-f",str(prompt_path),"-jf",str(schema_path),
             "--no-conversation","--offline","--no-display-prompt","--simple-io","--no-escape",
             "--no-warmup","--color","off","-c","4096","-n","1700","-ngl","auto",
             "--seed",str(seed%2147483647),"--temp",str(temperature)]
        result=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,timeout=1800,
                              creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    if result.returncode:
        raise RuntimeError("Прямой запуск llama.cpp завершился ошибкой. " + result.stderr.decode("utf-8",errors="replace")[-650:])
    out=result.stdout.decode("utf-8-sig",errors="replace")
    offset=out.find("{")
    if offset<0: raise ValueError("llama.cpp не вернул план в формате JSON")
    value,_=json.JSONDecoder().raw_decode(out[offset:])
    return {"message":{"content":json.dumps(value,ensure_ascii=False)}, "model":"Qwen3:8b GGUF" if model.name.startswith("sha256-a3de86cd1") or model.name=="qwen3-8b.gguf" else model.name,
            "engine":engine.name}


def native_available():
    try:
        _palace_native_files()
    except (OSError, RuntimeError, ValueError, KeyError):
        return False
    return True


def _palace_infer(prompt, style, seed, previous, backend):
    """Ask the installed model, validate its program, and allow it one correction."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Введите запрос для генерации комнаты")
    style = _palace_choice(style, PALACE_PROFILES)
    seed = int(seed)
    instruction = (
        "Design a baroque room. Respond with the requested compact JSON. Use the chosen regional interpretation and obey the brief. "
        "Design a ceiling from weighted rectangular strips (bands). X is the long room axis. Along axis x, successive bands run left to right: "
        "each band contains its own list of cells from bottom to top. Axis y interchanges these directions. "
        "The layout may range from one main field to a gallery of irregular sizes. Cells can use ornamental palette A, B, C or 'void' (plain). "
        "A/B/C have distinct shapes, sculptural motifs and 1-4 compatible detail elements. "
        "One band of one cell makes a whole-ceiling field. A triptych is three adjacent fields. "
        "For a dominant ceiling field, give its band and cell more weight. For corner pieces with a blank center, an example is bands [A void A],[void],[A void A]. "
        "Do not merely repeat one generic grid. Respect explicit numbers of fields. Keep strips broad enough to carve, coordinate wall bays and crowns. "
        "Specify quantities on scale 0..1. Return a short Russian title. Total nonvoid cells 1..16. Each cell axis >= 1/10 of the ceiling. "
        "In an edit keep unrelated features of the supplied program. "
        "An empty center requires a plain square extending 15% either side of center. All four corners means the four coordinates at ±0.76."
    )
    user_text = PALACE_PROFILES[style][1] + "\nЗадание: " + prompt.strip()
    if previous is not None:
        prior = previous.get("program")
        if not isinstance(prior, dict):
            raise ValueError("Для редактирования нужен сохраненный рецепт комнаты")
        user_text += "\nИзмените этот проект: " + json.dumps(prior, ensure_ascii=False, separators=(",", ":"))
    messages = [{"role": "system", "content": instruction}, {"role": "user", "content": user_text}]
    started = time.monotonic()
    for attempt in range(2):
        schema = _palace_schema()
        requested_count, empty_center, occupied_corners = _palace_expectations(prompt)
        if backend=="native" and requested_count:
            rule = "Your output must contain exactly %s nonvoid cells; bands are strips, not decorative panels." % requested_count
            axes = bool(re.search(r"вдоль|триптих|медальона?\s+в\s+ряд|длинн\w+ ос",prompt.lower()))
            if axes and requested_count<=5 and not (empty_center or occupied_corners):
                bands = schema["properties"]["bands"]
                bands.update(minItems=requested_count,maxItems=requested_count)
                cells = bands["items"]["properties"]["cells"]
                cells.update(minItems=1,maxItems=1)
                cells["items"]["properties"]["type"]=_palace_enum(("A","B","C"))
                rule+=" Use one band per field, one cell per band."
            messages[-1]["content"]+="\n"+rule
        if backend=="native" and attempt==0:
            sample=default_plan(style,seed)["program"]
            messages[0]["content"]+="\nJSON syntax illustration, create your own weights and cells: "+json.dumps(sample,ensure_ascii=False,separators=(",",":"))
        payload = {"model": PALACE_MODEL, "stream": False, "think": False, "format": schema,
                   "messages": messages, "options": {"num_ctx": 6144, "num_predict": 1700,
                   "temperature": .58 if attempt == 0 else .25, "seed": (seed + attempt) % 2147483647}}
        if backend=="native":
            answer=_palace_native_response(messages,payload["format"],seed+attempt,payload["options"]["temperature"])
        elif backend=="ollama-cli":
            env = dict(os.environ, OLLAMA_HOST="127.0.0.1:11434")
            command = ["ollama", "run", PALACE_MODEL, "--format", "json", "--think=false", "--hidethinking", "--nowordwrap"]
            content = "\n".join(m["role"] + ": " + m["content"] for m in messages)
            content += "\nVariation " + str(seed) + ". JSON schema: " + json.dumps(payload["format"], separators=(",", ":"))
            p = subprocess.run(command, input=content.encode("utf-8"), capture_output=True,
                               env=env, timeout=900, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if p.returncode:
                raise RuntimeError("Ollama CLI: " + p.stderr.decode("utf-8", errors="replace")[-400:])
            answer = {"message": {"content": p.stdout.decode("utf-8-sig").strip()}, "model": PALACE_MODEL}
        else:
            req = urllib.request.Request(PALACE_URL, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=900) as response:
                    answer = json.load(response)
            except (urllib.error.URLError, TimeoutError) as exc:
                raise RuntimeError("Локальная Ollama не ответила. Проверьте её запуск и модель " + PALACE_MODEL + ". " + str(exc)) from exc
        raw = answer["message"]["content"]
        try:
            plan = _palace_compile(json.loads(raw), style, seed, backend)
            _palace_check_intent(plan, prompt)
            _palace_focal(plan,prompt)
        except (KeyError, TypeError, ValueError) as exc:
            if attempt:
                raise ValueError("Qwen дважды предложил непригодную композицию. " + str(exc)) from exc
            messages.extend([{"role": "assistant", "content": raw},
                             {"role": "user", "content": "Repair the composition program. " + str(exc)}])
            continue
        plan.update(model=answer.get("model", PALACE_MODEL), prompt=prompt.strip(),
                    seconds=round(time.monotonic() - started, 2), attempts=attempt + 1)
        return plan


def generate_plan(prompt, style, seed, previous=None):
    return _palace_infer(prompt, style, seed, previous, "ollama")


def generate_plan_cli(prompt, style, seed, previous=None):
    """Installed Ollama executable; its own service is accessed over loopback."""
    return _palace_infer(prompt, style, seed, previous, "ollama-cli")


def generate_plan_native(prompt, style, seed, previous=None):
    """Run Qwen GGUF by opening a local model file, with sockets and services unnecessary."""
    return _palace_infer(prompt, style, seed, previous, "native")


def _palace_rule_bands(text, n, rng, empty, corners, clear):
    def row(w, cells):
        return {"weight": w, "cells": [{"weight": a, "type": b} for a,b in cells]}

    if clear or corners or empty:
        if corners and n < 4:
            raise ValueError("Для четырёх отдельных угловых украшений нужны хотя бы четыре поля")
        size = 3 if n <= 9 - int(empty) - 4*int(clear) else 5
        last, mid = size-1, size//2
        corner_slots = {(0,0), (0,last), (last,0), (last,last)}
        forbidden = ({(mid,mid)} if empty else set()) | (corner_slots if clear else set())
        chosen = set(corner_slots) if corners else set()
        cells = {(i,j) for i in range(size) for j in range(size)}
        if n > len(cells-forbidden):
            raise ValueError("Недостаточно места для заданного числа полей")
        if not empty and len(chosen) < n:
            chosen.add((mid,mid))
        # Fill reflected pairs before isolated cells. Sorting gives reproducible seeds.
        choices = sorted(cells-forbidden-chosen)
        rng.shuffle(choices)
        for i,j in choices:
            if len(chosen) >= n: break
            chosen.add((i,j))
            if len(chosen) < n and (last-i,last-j) not in forbidden:
                chosen.add((last-i,last-j))
        return [row(1, [(1, "void" if (i,j) not in chosen else "A" if i==j==mid else
                         "B" if (i,j) in corner_slots else "C") for j in range(size)]) for i in range(size)]
    axial = bool(re.search(r"ос[ьи]|триптих|анфилад|одн[ауой]+\s+лини|в\s+ряд", text))
    equal = bool(re.search(r"сетк|равномер|кессон", text))
    if axial and n <= 5:
        return [row(3 if i*2==n-1 else 2, [(1,"A" if i*2==n-1 else "B")]) for i in range(n)]
    if equal:
        factors = [(i,n//i) for i in range(1,6) if n%i==0 and n//i<=5]
        if factors:
            cols, rows = min(factors, key=lambda f: abs(f[0]-f[1]))
            return [row(1, [(1,"A" if i*2==cols-1 and j*2==rows-1 else "BC"[(i+j)%2])
                            for j in range(rows)]) for i in range(cols)]
    rows_count = rng.randint(max(1,(n+4)//5), min(5,n))
    sizes = [1]*rows_count
    for _ in range(n-rows_count):
        ix = rng.choice([i for i,v in enumerate(sizes) if v < 5])
        sizes[ix] += 1
    result = []
    for i, k in enumerate(sizes):
        band_weight = (3 if k==1 else 2) if rows_count%2 and i*2==rows_count-1 else rng.choice((1,2))
        result.append(row(band_weight, [(2 if k<=3 and j*2==k-1 else 1,
                            "A" if i==rows_count//2 and j==k//2 else rng.choice(("B","C"))) for j in range(k)]))
    return result


def _palace_tone(text, pattern):
    less = r"(?:меньше|мало|меньшим|бледн\w*|уба\w*|уменьш\w*|миним\w*|легк\w*|редк\w*)"
    more = r"(?:больше|много|большим|увелич\w*|усил\w*|добав\w*|гуще|густ\w*|обиль\w*|обильнее|богат\w*|насыщ\w*)"
    where = r"(?:\s+\w+){0,2}\s+"
    if re.search(less+where+pattern+"|"+pattern+where+less,text): return -.25
    if re.search(more+where+pattern+"|"+pattern+where+more,text): return .25
    return 0.


def local_plan(prompt, style, seed, previous=None):
    """Run the Russian rule grammar entirely in process. No neural runtime or service."""
    text = str(prompt or "").lower().replace("ё","е").strip()
    if not text:
        raise ValueError("Введите запрос для генерации комнаты")
    style = _palace_choice(style, PALACE_PROFILES)
    rng = random.Random(int(seed) ^ int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big"))
    prior = previous if previous and previous.get("style") == style else None
    program = copy.deepcopy((prior or default_plan(style,seed))["program"])
    notes = []
    wall_text = bool(re.search(r"стен[а-я]*|простен\w*|портал\w*|пилястр\w*",text))
    ceiling_text = bool(re.search(r"потол\w*|плафон\w*|потолк\w*",text))
    wall_only = wall_text and not ceiling_text
    ceiling_only = ceiling_text and not wall_text
    if re.search(r"(?:только|лишь)\s+стен|потол(?:ок|ка)\s+не\s+(?:трог|меня)",text): wall_only,ceiling_only=True,False
    if re.search(r"(?:только|лишь)\s+(?:плафон|потол)|стен\w*\s+не\s+(?:трог|меня)",text): wall_only,ceiling_only=False,True
    count, empty, corners = _palace_expectations(text)
    clear = _palace_clear_corners(text)
    new_composition = bool(re.search(r"композиц|перестро|друг\w+\s+(?:плафон|потолок|схем)|заново|вариант",text))
    if not wall_only and (not prior or count or empty or corners or clear or new_composition):
        n = count if count is not None else 4 if corners and empty else (
            rng.choice((3,5,7,9)) if style!="mexican" else rng.choice((5,7,9,12)))
        if not 1 <= n <= 16: raise ValueError("В этой версии возможно от 1 до 16 потолочных полей")
        program["axis"] = "y" if re.search(r"попер[её]к|коротк\w*\s+ос",text) else (
            "x" if re.search(r"ос[ьи]|триптих|вдоль",text) else rng.choice(("x","y")))
        program["bands"] = _palace_rule_bands(text,n,rng,empty,corners,clear)
        notes.append("полей %d" % n)
        if empty: notes.append("пустой центр")
        if clear: notes.append("пустые углы")
        if corners: notes.append("четыре угловые зоны")
    if not ceiling_only:
        for pattern,rhythm in [(r"черед\w*|разношир\w*","alternating"),(r"равномер\w*|равн\w*\s+шаг","uniform"),(r"осев\w*|парадн\w*|процесси\w*","processional")]:
            if re.search(pattern,text):
                program["wall_rhythm"]=rhythm
                notes.append("ритм стен " + rhythm)
                break
        bays = re.search(r"\b([2-5]|дв[ае]|три|четыре|пять)\s+(?:настенн\w+\s+)?(?:ар(?:ки|ок)|пролет\w*|секци\w*|простенк\w*)\b",text)
        if bays:
            words={"два":2,"две":2,"три":3,"четыре":4,"пять":5}
            program["wall_bays"]=int(bays[1]) if bays[1].isdigit() else words[bays[1]]
            notes.append("пролётов %d" % program["wall_bays"])
    descriptors = ([] if ceiling_only else [program["wall"]]) + ([] if wall_only else list(program["palette"].values()))
    motifs = [m for pat,m in [(r"раковин|ракуш","shell"),(r"лучист|солнеч|звезд","sunburst"),
             (r"лоз[а-ю]|виноград","vine"),(r"цвето[чк]|цветоч|цвет[ыа]","flower")] if re.search(pat,text)]
    shapes = [s for pat,s in [(r"овал","oval"),(r"восьмигран|восьмиугол","octagon"),(r"лопаст|волнист","lobed"),(r"арочн|арками","arch"),(r"прямоуголь","rect")] if re.search(pat,text)]
    for i, d in enumerate(descriptors):
        if motifs: d["motif"]=motifs[i%len(motifs)]
        if shapes: d["shape"]=shapes[i%len(shapes)]
        for pattern,element in [(r"бусин|жемчуг","beads"),(r"ветв|веточ|гирлянд","spray"),(r"веер","fan"),(r"волют|завит","scroll"),(r"розетк","rosette")]:
            if re.search(pattern,text): d["elements"] = [element]+[e for e in d["elements"] if e!=element][:3]
    notes.extend(motifs+shapes)
    levels=("curl","foliage","gilding")
    target_zones=["wall"] if wall_only else ["ceiling"] if ceiling_only else ["wall","ceiling"]
    tuning={zone:dict((prior or {}).get("zone_tuning",{}).get(zone, {k:program[k] for k in levels})) for zone in ("wall","ceiling")}
    changes={k:_palace_tone(text,v) for k,v in zip(levels,[r"(?:завит\w*|волют\w*)",r"(?:листв\w*|лист\w*|листь\w*|лепнин\w*|ветв\w*)",r"(?:золот\w*|позолот\w*|золоч\w*)"])}
    if re.search(r"пышн|насыщенн\w*\s+лепнин|богат\w*\s+резьб",text): changes["foliage"]=.24
    for k,delta in changes.items():
        zero = k=="gilding" and re.search(r"без\s+(?:позолот|золот)|убер\w*\s+(?:всю\s+)?позолот",text)
        if zero or delta:
            for zone in target_zones:
                tuning[zone][k]=0. if zero else round(max(0.,min(1.,tuning[zone][k]+delta)),3)
            if len(target_zones)==2: program[k]=tuning["ceiling"][k]
            notes.append(k)
    program["title"] = PALACE_PROFILES[style][0] + " · " + str(seed)
    plan=_palace_compile(program,style,seed,"procedural_prompt")
    if not wall_only:
        _palace_check_intent(plan,prompt)
        _palace_focal(plan,prompt)
    if len(target_zones)==1 or (prior and prior.get("zone_tuning")): plan["zone_tuning"]=tuning
    plan.update(prompt=prompt, interpretation=list(dict.fromkeys(notes)), attempts=1)
    return plan


def _palace_similarity(a,b):
    union = a|b
    return len(a&b)/len(union) if union else 1.


def _palace_content(plan):
    keys=("style","layout","wall_bays","wall_rhythm","wall_shape","wall_motif","wall_elements","foliage","curl","gilding","zone_tuning")
    return json.dumps({k:plan.get(k) for k in keys}, sort_keys=True, ensure_ascii=False)


def generate_best(prompt, style, seed, previous=None, attempts=3, backend="ollama"):
    """Build 1..4 drafts then choose using geometry. Paid/network services are never used."""
    evaluators={"ollama":generate_plan, "rules":local_plan, "ollama-cli":generate_plan_cli, "native":generate_plan_native}
    evaluator=evaluators[_palace_choice(backend,evaluators)]
    count=_palace_number(attempts,1,4,True)
    accepted, records = [], []
    prior_signature = _palace_content(previous) if previous else None
    previous_mask = _palace_mask(previous) if previous else None
    started=time.monotonic()
    for i in range(count):
        candidate_seed=int(seed)+7919*i
        record={"seed":candidate_seed}
        try:
            p=evaluator(prompt,style,candidate_seed,previous)
            if prior_signature and _palace_content(p)==prior_signature:
                raise ValueError("Все редактируемые свойства совпадают с исходной комнатой")
            mask=_palace_mask(p)
            coverage=len(mask)/2401.
            biggest=max(c["rx"]*c["ry"] for c in p["layout"])
            smallest=min(c["rx"]*c["ry"] for c in p["layout"])
            hierarchy=biggest/max(smallest,.00001)
            uniform=bool(re.search(r"равномер|сетк|одинаков|кессон",prompt.lower()))
            target_coverage={"bavarian":.38,"russian":.49,"mexican":.55}[style]
            target_hierarchy=1. if uniform else 2.7
            score=1.-.65*abs(coverage-target_coverage)-.16*min(1,abs(math.log(hierarchy/target_hierarchy)))
            record.update(title=p["title"], fields=len(p["layout"]), coverage=round(coverage,3), hierarchy=round(hierarchy,2))
            if previous_mask:
                record["similarity_to_previous"]=round(_palace_similarity(mask,previous_mask),3)
            closest=max((_palace_similarity(mask,m) for _,m,_ in accepted),default=0.)
            record["similarity_to_earlier"]=round(closest,3)
            # Count nearly identical plans with different scrolling as one ceiling alternative.
            if closest>.95:
                raise ValueError("Силуэт потолочных полей повторяет уже рассмотренную композицию")
            record["score"]=round(score,4)
            accepted.append((p,mask,score))
        except (ValueError, KeyError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
            record["reason"]=str(exc)
        records.append(record)
    if not accepted:
        raise ValueError("Подходящей комнаты нет. " + " / ".join(dict.fromkeys(r.get("reason","") for r in records))[:500])
    best=max(accepted,key=lambda item:item[2])[0]
    best["selection"]={"backend":backend, "tried":count, "selected_seed":best["seed"], "candidates":records,
                       "seconds":round(time.monotonic()-started,2)}
    return best
