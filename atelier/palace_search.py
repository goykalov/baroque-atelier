"""Search through baroque room architectures with a deadline and an offline critic."""
import copy
import json
import math
import os
from pathlib import Path
import random
import re
import secrets
import subprocess
import tempfile
import time

if "_palace_compile" not in globals():
    from palace_plan import (
        PALACE_PROFILES, _palace_compile, _palace_check_intent, _palace_focal,
        _palace_expectations, _palace_clear_corners, _palace_mask, _palace_similarity,
        _palace_schema, _palace_native_files, local_plan,
    )
    from palace_auto import _ultra_random_draft, _ultra_spec, _dense_tuning, _ultra_school
    from palace_architecture import ARCH_WALLS, ARCH_CEILINGS, ARCH_LABELS
    from palace_art import assign_palace_paintings


HALL_LAYOUTS=("radial","procession","diagonal","islands","banded","cross")
HALL_PROFILE_LABELS={"radial":"венец","procession":"анфилада","diagonal":"диагональ",
                     "islands":"острова","banded":"продольные поля","cross":"крестовая схема"}
HALL_BUDGETS=(60,600,3600)


def architecture_checked(spec):
    if not isinstance(spec,dict) or spec.get("walls") not in ARCH_WALLS or spec.get("ceiling") not in ARCH_CEILINGS:
        raise ValueError("Неизвестный тип опор или свода")
    order=spec.get("order")
    if type(order) is not int or not 3<=order<=5:
        raise ValueError("Число ярусов должно быть 3–5")
    result={k:spec[k] for k in ("walls","ceiling","order")}
    for k,lo in (("reach",.35),("asymmetry",0.)):
        v=spec.get(k)
        if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=1:
            raise ValueError("Некорректная пропорция «"+k+"»")
        result[k]=v
    return result


def validate_hall_layout(layout):
    shapes=("oval","lobed","octagon","arch","rect")
    motifs=("shell","sunburst","vine","flower")
    elements=("shell","fan","spray","beads","rosette","scroll")
    if not isinstance(layout,list) or not 1<=len(layout)<=16:
        raise ValueError("Зал должен иметь от одного до шестнадцати потолочных полей")
    ids=set()
    for p in layout:
        key=p.get("id")
        if not isinstance(key,str) or not re.fullmatch(r"p[0-9]+(?:_[0-9]+)?",key) or key in ids:
            raise ValueError("Некорректные имена потолочных полей")
        ids.add(key)
        if p.get("shape") not in shapes or p.get("motif") not in motifs or not 1<=len(p.get("elements",[]))<=4 or any(e not in elements for e in p["elements"]):
            raise ValueError("Неизвестная форма орнамента")
        if any(type(p[k]) not in (int,float) or not math.isfinite(p[k]) for k in ("x","y","rx","ry")):
            raise ValueError("Нечисловое положение потолочного поля")
        if min(p["rx"],p["ry"])<.064 or abs(p["x"])+p["rx"]>1.001 or abs(p["y"])+p["ry"]>1.001:
            raise ValueError("Поле вышло за границы орнаментальной зоны")
    for i,p in enumerate(layout):
        for q in layout[:i]:
            if abs(p["x"]-q["x"])<p["rx"]+q["rx"]-.001 and abs(p["y"]-q["y"])<p["ry"]+q["ry"]-.001:
                raise ValueError("Потолочные поля перекрываются")
    return layout


def hall_history_item(plan):
    return {k:plan[k] for k in ("architecture","layout","wall_shape","wall_bays","pattern","paintings") if k in plan}


def _hall_places(pattern,arch,rng):
    a=arch["asymmetry"]; n=arch["order"]; r=arch["reach"]
    points=[]
    def put(x,y,rx,ry,name):
        points.append((round(x,6),round(y,6),round(rx,6),round(ry,6),name))
    if pattern=="radial":
        c=.31+.075*r
        put(0,0,c,c*.88,"A")
        for i in range(4):
            theta=math.pi*i/2
            put(.68*math.cos(theta),.68*math.sin(theta),.16+.04*r,.17+.035*r,"B" if i%2 else "C")
    elif pattern=="cross":
        put(0,0,.59,.21,"A")
        for side in (-1,1):
            put(0,side*.59,.30,.24,"B")
            put(side*.78,0,.146,.24,"C")
    elif pattern=="procession":
        c=.32+.15*r
        put(0,0,c,.51+.14*r,"A")
        for hand in (-1,1):
            sx=.69+.04*r
            put(hand*sx,0,max(.113,.925-sx),.40+.15*r,"B" if hand<0 or a<.55 else "C")
    elif pattern=="banded":
        for i in range(n):
            u=2*(i+.5)/n-1
            put(u*.95,0,(.91/n),.48+.31*math.cos(u*1.27),("B","A","C")[i%3])
    elif pattern=="diagonal":
        width=.22+.06*r
        put(.01,-.025,width,width,"A")
        for side in (-1,1):
            put(.63*side,.56*side,.28,.28,"B")
            put(-.63*side,.46*side,.22*a+.065,.15,"C")
    elif pattern=="islands":
        put(rng.uniform(-.08,.08)*a,.09*a,.29+.055*r,.27+.03*r,"A")
        for i,(x,y) in enumerate(((-.66,-.57),(.63,-.57),(-.65,.55),(.64,.58),(-.69,.0),(.71,.04),(0,-.64),(0,.68))):
            if i>=4 and rng.random()<.45:continue
            pop=(x+rng.uniform(-.025,.025)*a,y+rng.uniform(-.015,.015)*a,
                 rng.uniform(.15,.23),rng.uniform(.12,.207),"B" if i%2 else "C")
            if all(abs(x0-pop[0])>rx+pop[2]+.015 or abs(y0-pop[1])>ry+pop[3]+.015 for x0,y0,rx,ry,_ in points):
                put(*pop)
    if rng.random()<.40 and pattern!="radial":
        points=[(y,x,ry,rx,key) for x,y,rx,ry,key in points]
    return points


def _hall_random_spec(rng):
    return {"walls":rng.choice(ARCH_WALLS),"ceiling":rng.choice(ARCH_CEILINGS),
            "order":rng.choice((3,4,5)),"reach":round(rng.uniform(.51,1),2),"asymmetry":round(rng.uniform(.26,.98),2),
            "layout":rng.choice(HALL_LAYOUTS),"motif":rng.choice(("sunburst","shell","vine","flower")),
            "art":rng.choice((1,2,3)),"growth":round(rng.uniform(.95,1.29),2),
            "edit":""}


def _hall_hard_intent(prompt):
    count,empty,corners=_palace_expectations(prompt)
    return bool(count is not None or empty or corners or _palace_clear_corners(prompt.lower()))


def _hall_compile(spec,style,seed,brief,previous,art_history,size_m):
    tuning=architecture_checked(spec)
    pattern=spec["layout"]
    motif=spec["motif"]
    if pattern not in HALL_LAYOUTS or motif not in ("sunburst","shell","vine","flower"):
        raise ValueError("Неизвестный рисунок плафона")
    if type(spec["art"]) is not int or not 0<=spec["art"]<=4 or type(spec["growth"]) not in (int,float) or not .8<=spec["growth"]<=1.3:
        raise ValueError("Недопустимая плотность или число росписей")
    preserve=bool(previous and re.search(r"только\s+стен|потол\w*\s+не\s+(?:мен|трог)",brief.lower()))
    if preserve or _hall_hard_intent(brief):
        plan=local_plan(brief,style,seed,previous)
    else:
        rng=random.Random(seed ^ 128)
        plan=_ultra_random_draft(style,seed)
        points=_hall_places(pattern,tuning,rng)
        program=plan["program"]
        palette=program["palette"]
        palette["A"]=dict(palette["A"],shape="lobed" if pattern in ("radial","diagonal") else palette["A"]["shape"],
                          motif=motif)
        # The four identical satellites do not force the walls to be symmetrical.
        if pattern=="radial":
            for name in ("B","C"):
                palette[name]=dict(palette[name],shape="oval",motif="flower",elements=["beads","rosette"])
        plan["layout"]=[dict(palette[key],id="p"+str(i+1),x=x,y=y,rx=rx,ry=ry)
                        for i,(x,y,rx,ry,key) in enumerate(points)]
        if previous and re.search(r"только\s+потол|стен\w*\s+не\s+(?:мен|трог)",brief.lower()):
            for k in ("wall_bays","wall_shape","wall_rhythm","wall_motif","wall_elements"):plan[k]=previous[k]
            for k in ("wall","wall_bays","wall_rhythm"):program[k]=copy.deepcopy(previous["program"][k])
            tuning["walls"]=previous.get("architecture",{}).get("walls",tuning["walls"])
    if preserve:
        plan["layout"]=copy.deepcopy(previous["layout"])
        if "architecture" in previous:
            tuning["ceiling"]=previous["architecture"]["ceiling"]
        pattern=previous.get("pattern",pattern)
    validate_hall_layout(plan["layout"])
    _palace_check_intent(plan,brief)
    _palace_focal(plan,brief)
    plan["prompt"]=brief
    plan["architecture"]=tuning
    plan["pattern"]=pattern
    plan["ultra"]=_ultra_spec(plan,brief,previous.get("ultra") if previous else None)
    plan["dense"]=_dense_tuning(plan,brief,previous)
    plan["dense"].update(growth=spec["growth"],order=min(tuning["order"],4),rhythm=tuning["asymmetry"])
    plan["paintings"]=copy.deepcopy(previous.get("paintings",{})) if preserve else assign_palace_paintings(plan,spec["art"],art_history)
    plan["title"]=ARCH_LABELS[tuning["walls"]].capitalize()+" · "+ARCH_LABELS[tuning["ceiling"]]
    plan["source"]="architecture_rules"
    plan["export_note"]=str(spec.get("edit",""))[:280]
    return plan


def _hall_score(plan,archive,mask,old_masks,size):
    # Use geometric footprint and topology; palette and texture are deliberately absent.
    a=plan["architecture"]
    base=min(.69,len(mask)/2401)
    areas=sorted((p["rx"]*p["ry"] for p in plan["layout"]),reverse=True)
    hierarchy=areas[0]/max(.01,sum(areas))
    constructive=.10-.35*abs(base-.48)+.18*(1.-abs(hierarchy-.4))
    if size and min(size[:2])<4.5 and a["walls"] in ("gallery","pilasters"):
        constructive-=.07
    novelty=[]
    for old,old_mask in zip(archive,old_masks):
        b=old.get("architecture",{})
        same_pair=a["walls"]==b.get("walls") and a["ceiling"]==b.get("ceiling")
        shape_delta=1.-_palace_similarity(mask,old_mask)
        if same_pair and shape_delta<.28:
            return None
        novelty.append(.46*(a["walls"]!=b.get("walls"))+.28*(a["ceiling"]!=b.get("ceiling"))+.26*shape_delta)
    diversity=min(novelty,default=.69)
    return round(constructive+.65*diversity,6)


def _hall_json_schema(exclude=None):
    enum=lambda xs:{"type":"string","enum":list(xs)}
    integer=lambda lo,hi:{"type":"integer","minimum":lo,"maximum":hi}
    number=lambda lo,hi:{"type":"number","minimum":lo,"maximum":hi}
    props={"walls":enum(ARCH_WALLS),"ceiling":enum(ARCH_CEILINGS),"order":integer(3,5),
           "reach":number(.35,1),"asymmetry":number(0,1),"layout":enum(HALL_LAYOUTS),
           "motif":enum(("shell","sunburst","vine","flower")),"art":integer(0,4),
           "growth":number(.8,1.3),"edit":{"type":"string","maxLength":280}}
    if exclude:
        key,value=exclude
        props[key]["enum"].remove(value)
    return {"type":"object","properties":props,"required":list(props),"additionalProperties":False}


def _hall_local_model(engine,model_file,label,brief,proposal,remaining,seed,cap,exclude,finish):
    instruction=(
        "You compose a baroque room within existing dimensions. Choose a coherent spatial relationship, "
        "with structural silhouette (not repainting), deep mouldings, visual hierarchy and controlled gaps. "
        "Walls: arcade=linked structural arches, pilasters=paired twisted columns, alcoves=exedras, "
        "gallery=upper gallery, canopy=projecting curved baldachins, grotto=organic sculptural archwork. "
        "Ceilings: star=radial sculpted web, rib_vault=barrel ribs, garlands=waves, "
        "woven=interlacing, shells=scalloped relief, cassettes=deep coffers. "
        "Layout radial has four satellites; procession has three large axial fields; "
        "cross forms a transverse intersection; banded makes long bands; diagonal offers an oblique axis; "
        "islands are uneven clustered fields. Edit should briefly say in Russian what spatial change you made and why. "
        "Take user constraints seriously. Use numbers within the format. Return only JSON."
    )
    def escape(value):
        return value.replace("<|im_", "< im_").replace("<think>", "< think >")
    text=("<|im_start|>system\n"+instruction+"<|im_end|>\n<|im_start|>user\n"
          +escape(brief)+"\n"+escape(json.dumps(proposal,ensure_ascii=False,separators=(",",":")))
          +"<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n")
    with tempfile.TemporaryDirectory(prefix="palace-search-") as temp:
        root=Path(temp)
        inp,grammar=root/"brief.txt",root/"schema.json"
        inp.write_text(text,encoding="utf8")
        grammar.write_text(json.dumps(_hall_json_schema(exclude)),encoding="utf8")
        cmd=[str(engine),"-m",str(model_file),"-f",str(inp),"-jf",str(grammar),
             "--no-conversation","--offline","--no-display-prompt","--simple-io","--no-escape",
             "--no-warmup","--color","off","-c","2560","-n","420","-ngl","auto",
             "--seed",str(seed%2147483647),"--temp",".78"]
        limit=max(.1,min(remaining,cap))
        with subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                              creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)) as p:
            deadline=time.monotonic()+limit
            while True:
                try:
                    out,err=p.communicate(timeout=min(.8,max(.1,deadline-time.monotonic())))
                    break
                except subprocess.TimeoutExpired:
                    if (finish and finish()) or time.monotonic()>=deadline:
                        p.kill()
                        p.communicate()
                        raise subprocess.TimeoutExpired(engine.name,round(limit))
            if p.returncode:
                raise RuntimeError(label+" · "+err.decode("utf8",errors="replace")[-260:].strip())
    body=out.decode("utf8",errors="replace")
    start=body.find("{")
    if start<0:raise ValueError("Модель не вернула композицию")
    return json.JSONDecoder().raw_decode(body[start:])[0]


def search_hall(prompt="",style="random",seed=None,previous=None,budget=60,history=(),
                progress=None,backend="native",size_m=None,finish=None):
    """Select the best valid geometry recipe found before the search deadline."""
    if budget not in HALL_BUDGETS:
        raise ValueError("Выберите 1, 10 или 60 минут")
    if backend not in ("native","rules"):
        raise ValueError("Неизвестный локальный режим поиска")
    progress=progress or (lambda message:None)
    started=time.monotonic()
    deadline=started+budget
    seed=secrets.randbelow(2**30) if seed is None else int(seed)
    rng=random.Random(seed)
    prompt=(prompt or "").strip()
    old=list(history)[-12:]
    avoid_art={t for u in old[-2:] for t in u.get("paintings",{}).values()}
    masks=[_palace_mask(u) for u in old]
    pool=[]
    notes=[]
    explicit_style=_ultra_school(prompt,style,random.Random(0)) if (style!="random" or re.search(r"бавар|амалиенбург|нимфенбург|немецк|русск|растрелли|елизаветин|екатерининск|мексик|пуэбл|новоиспан|ретабло",prompt.lower())) else None
    if previous and not explicit_style:explicit_style=previous["style"]

    def accept(spec,tick,label,school):
        trial_seed=seed+7919*tick
        p=_hall_compile(spec,school,trial_seed,prompt,previous,avoid_art,size_m)
        score=_hall_score(p,old,_palace_mask(p),masks,size_m)
        if score is None:raise ValueError("Слишком близко к залу из истории")
        p.update(seed=int(trial_seed),input_seed=seed,source=label)
        pool.append((score,p,spec))
        return score

    progress("Строятся и сравниваются компоновки")
    total={60:24,600:72,3600:144}[budget]
    for i in range(total):
        spec=_hall_random_spec(rng)
        try:
            score=accept(spec,i,"architecture_rules",explicit_style or rng.choice(tuple(PALACE_PROFILES)))
        except ValueError as error:
            if i<4:notes.append({"phase":"layout","error":str(error)})
    if not pool:
        raise ValueError("Не найден допустимый эскиз "+str(notes[:2]))
    # Two roles of the same locally loaded model, with serial proposal/critique passes.
    inference=None
    if backend=="native":
        try:inference=_palace_native_files()
        except (ValueError,RuntimeError,OSError) as error:notes.append({"phase":"model","error":str(error)})
    local_completed=0
    stop="rules_only" if backend=="rules" else "model_unavailable" if inference is None else "completed_passes"
    rounds={60:2,600:22,3600:108}[budget]
    stage_school=explicit_style or max(pool,key=lambda item:item[0])[1]["style"]
    used_signatures=set()
    repeats=0
    for i in range(rounds if inference else 0):
        if finish and finish():
            stop="accepted_early"
            break
        remaining=deadline-time.monotonic()
        if remaining<4:
            stop="time_budget"
            break
        progress(f"Qwen · {'предложение' if i==0 else 'критика и перестройка'} {i+1} · до {math.ceil(remaining)} с")
        base=sorted(pool,key=lambda item:item[0],reverse=True)[:3]
        axis=("walls","ceiling","layout")[i%3]
        exclude=(axis,base[0][2][axis]) if i else None
        context={"hall_m":size_m,"base":[{"draft":x[2],"score":x[0]} for x in base],
                 "avoid_recent":[u.get("architecture",{}) for u in old[-5:]],
                 "already_tried":[x.get("architecture") for x in notes[-4:] if x.get("architecture")],
                 "replace":exclude,
                 "task":"Invent a substantially different architecture" if i==0 else
                 "Critique the best draft, replace the indicated element, and improve the alignment of framing with the new structure."}
        step={"phase":"proposal" if i==0 else "critique","local_model":"Qwen3 8B"}
        t=time.monotonic()
        try:
            spec=_hall_local_model(*inference,"Qwen3 8B",prompt or "Выразительный непохожий барочный зал.",
                                   context,remaining-1,seed+i,{60:34,600:100,3600:155}[budget],exclude,finish)
            sig=tuple(spec[k] for k in ("walls","ceiling","layout","order"))
            step.update(architecture={k:spec[k] for k in ("walls","ceiling","layout")},
                        comment=spec.get("edit",""))
            if sig in used_signatures:
                repeats+=1
                raise ValueError("Локальная модель повторила скелет композиции")
            used_signatures.add(sig)
            step["score"]=accept(spec,total+i,"architecture_qwen",stage_school)
            local_completed+=1
        except (RuntimeError,OSError,KeyError,TypeError,ValueError,subprocess.SubprocessError) as error:
            step["error"]=str(error)[:380]
            if isinstance(error,subprocess.TimeoutExpired):stop="time_budget" if deadline-time.monotonic()<4 else "model_timeout"
        step["seconds"]=round(time.monotonic()-t,2)
        notes.append(step)
        if finish and finish():
            stop="accepted_early"
            break
        if repeats>={60:2,600:8,3600:17}[budget] and local_completed>=3:
            stop="repeated_structures"
            break
    # Use model work when it delivers a valid alternative within a small margin of the objective best.
    best=max(pool,key=lambda item:item[0])
    neural=[p for p in pool if p[1]["source"]=="architecture_qwen" and p[0]>=best[0]-.12]
    if neural:best=max(neural,key=lambda item:item[0])
    result=best[1]
    result["search"]={"budget_s":budget,"elapsed_s":round(time.monotonic()-started,2),
                      "procedural_drafts":total,"valid_recipes":len(pool),"ai_passes":local_completed,
                      "selected":result["source"],"score":best[0],"stop":stop,"trace":notes}
    return result
