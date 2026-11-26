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
        _palace_expectations, _palace_clear_corners, _palace_inside, _palace_mask, _palace_similarity,
        _palace_schema, _palace_native_files, local_plan,
    )
    from palace_auto import _ultra_random_draft, _ultra_spec, _dense_tuning, _ultra_school
    from palace_architecture import ARCH_WALLS, ARCH_CEILINGS, ARCH_LABELS, HALL_SECTIONS
    from palace_art import assign_palace_paintings
    from palace_refinement import refinement_checked, refine_hall
    from palace_ensemble import search_ensemble


HALL_LAYOUTS=("radial","procession","diagonal","islands","banded","cross")
HALL_PROFILE_LABELS={"radial":"венец","procession":"анфилада","diagonal":"диагональ",
                     "islands":"острова","banded":"продольные поля","cross":"крестовая схема"}
HALL_BUDGETS=(60,600,3600)
HALL_SCOPES=("hall","ceiling","portal")


def architecture_checked(spec):
    if not isinstance(spec,dict) or spec.get("walls") not in ARCH_WALLS or spec.get("ceiling") not in ARCH_CEILINGS:
        raise ValueError("Неизвестный тип опор или свода")
    order=spec.get("order")
    if type(order) is not int or not 3<=order<=5:
        raise ValueError("Число ярусов должно быть 3–5")
    result={k:spec[k] for k in ("walls","ceiling","order")}
    if "section" in spec:
        if spec["section"] not in HALL_SECTIONS:
            raise ValueError("Неизвестный разрез зала")
        result["section"]=spec["section"]
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
    return {k:plan[k] for k in ("architecture","layout","wall_shape","wall_motif","wall_bays","wall_rhythm","pattern","paintings") if k in plan}


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
            "section":rng.choice(HALL_SECTIONS),"bays":rng.randint(3,6),
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
    if "bays" in spec:
        bays=spec["bays"]
        if type(bays) is not int or not 3<=bays<=6:
            raise ValueError("Нужно от трёх до шести пролётов")
        if not previous or not re.search(r"только\s+потол|стен\w*\s+не\s+(?:мен|трог)",brief.lower()):
            plan["wall_bays"]=plan["program"]["wall_bays"]=bays
    validate_hall_layout(plan["layout"])
    _palace_check_intent(plan,brief)
    _palace_focal(plan,brief)
    plan["prompt"]=brief
    plan["architecture"]=tuning
    plan["pattern"]=pattern
    plan["ultra"]=_ultra_spec(plan,brief,previous.get("ultra") if previous else None)
    plan["dense"]=_dense_tuning(plan,brief,previous)
    plan["dense"].update(growth=spec["growth"],order=min(tuning["order"],4),rhythm=tuning["asymmetry"])
    reserved=set()
    for clause in re.split(r"[.!?;]",brief.lower()):
        if re.search(r"центр|середин",clause) and re.search(r"розет|лепнин|ветвящ",clause):
            reserved.update(field["id"] for field in plan["layout"] if _palace_inside(field,0,0))
    plan["paintings"]=copy.deepcopy(previous.get("paintings",{})) if preserve else assign_palace_paintings(plan,spec["art"],art_history,reserved)
    plan["title"]=ARCH_LABELS[tuning["walls"]].capitalize()+" · "+ARCH_LABELS[tuning["ceiling"]]
    plan["source"]="architecture_rules"
    plan["export_note"]=str(spec.get("edit",""))[:280]
    return plan


def _hall_score(plan,archive,mask,old_masks,size,scope):
    # Use geometric footprint and topology; palette and texture are deliberately absent.
    a=plan["architecture"]
    base=min(.69,len(mask)/2401)
    areas=sorted((p["rx"]*p["ry"] for p in plan["layout"]),reverse=True)
    hierarchy=areas[0]/max(.01,sum(areas))
    constructive=.10-.35*abs(base-.48)+.18*(1.-abs(hierarchy-.4))
    if size and min(size[:2])<4.5 and a["walls"] in ("gallery","pilasters"):
        constructive-=.07
    novelty=[]
    if scope=="portal":
        return round(.20*plan["foliage"]+.12*plan["dense"]["growth"]+
                     .10*(plan["wall_motif"]!=archive[-1].get("wall_motif") if archive else True),6)
    for old,old_mask in zip(archive,old_masks):
        b=old.get("architecture",{})
        shape_delta=1.-_palace_similarity(mask,old_mask)
        ceiling_delta=(.38*(a["ceiling"]!=b.get("ceiling"))+
                       .20*(plan["pattern"]!=old.get("pattern"))+.42*shape_delta)
        if scope=="ceiling":
            distance=ceiling_delta
        else:
            wall_delta=(.49*(a["walls"]!=b.get("walls"))+.20*(a.get("section")!=b.get("section"))+
                        .20*min(1.,abs(plan["wall_bays"]-old.get("wall_bays",3))/2)+
                        .11*(plan["wall_rhythm"]!=old.get("wall_rhythm")))
            distance=.62*wall_delta+.38*ceiling_delta
        if distance<.08:
            return None
        novelty.append(distance)
    diversity=min(novelty,default=.69)
    return round(constructive+.65*diversity,6)


def _hall_json_schema(exclude=None):
    enum=lambda xs:{"type":"string","enum":list(xs)}
    integer=lambda lo,hi:{"type":"integer","minimum":lo,"maximum":hi}
    number=lambda lo,hi:{"type":"number","minimum":lo,"maximum":hi}
    props={"walls":enum(ARCH_WALLS),"ceiling":enum(ARCH_CEILINGS),"section":enum(HALL_SECTIONS),
           "bays":integer(3,6),"order":integer(3,5),
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
        "Section: vertical=tall architectural order, tiered=lower panels and strong horizontal divisions, "
        "swept=alternating heights and soft wall rhythm. Bays is the number of bays on the long walls. "
        "Layout radial has four satellites; procession has three large axial fields; "
        "cross forms a transverse intersection; banded makes long bands; diagonal offers an oblique axis; "
        "islands are uneven clustered fields. Edit should briefly say in Russian what spatial change you made and why. "
        "Take user constraints seriously. Use numbers within the format. Return only JSON."
    )
    return _hall_json_response(engine,model_file,label,instruction,brief,proposal,
                               remaining,seed,cap,_hall_json_schema(exclude),finish)


def _hall_json_response(engine,model_file,label,instruction,brief,proposal,remaining,seed,cap,schema,finish):
    def escape(value):
        return value.replace("<|im_", "< im_").replace("<think>", "< think >")
    text=("<|im_start|>system\n"+instruction+"<|im_end|>\n<|im_start|>user\n"
          +escape(brief)+"\n"+escape(json.dumps(proposal,ensure_ascii=False,separators=(",",":")))
          +"<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n")
    with tempfile.TemporaryDirectory(prefix="palace-search-") as temp:
        root=Path(temp)
        inp,grammar=root/"brief.txt",root/"schema.json"
        inp.write_text(text,encoding="utf8")
        grammar.write_text(json.dumps(schema),encoding="utf8")
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


def _search_hall_baseline(prompt,style,seed,previous,budget,history,progress,backend,size_m,finish,checkpoint,scope):
    """Select the architectural composition with the original one-minute algorithm."""
    if budget not in HALL_BUDGETS:
        raise ValueError("Выберите 1, 10 или 60 минут")
    if backend not in ("native","rules") or scope not in HALL_SCOPES:
        raise ValueError("Неизвестный режим или зона поиска")
    progress=progress or (lambda message:None)
    finish=finish or (lambda:False)
    started=time.monotonic()
    deadline=started+budget
    seed=secrets.randbelow(2**30) if seed is None else int(seed)
    rng=random.Random(seed)
    prompt=(prompt or "").strip()
    old=list(history)[-12:]
    avoid_art={art for item in old[-2:] for art in item.get("paintings",{}).values()}
    masks=[_palace_mask(item) for item in old]
    pool=[]
    notes=[]
    visited=set()
    procedural=local_completed=0
    published=None
    explicit_style=_ultra_school(prompt,style,random.Random(0)) if (style!="random" or re.search(
        r"бавар|амалиенбург|нимфенбург|немецк|русск|растрелли|елизаветин|екатерининск|мексик|пуэбл|новоиспан|ретабло",prompt.lower())) else None
    if previous and not explicit_style:
        explicit_style=previous["style"]

    def accept(spec,label,school):
        trial_seed=seed+7919*(procedural+2*len(notes))
        brief=prompt if scope!="portal" else ""
        candidate=_hall_compile(spec,school,trial_seed,brief,previous,avoid_art,size_m)
        score=_hall_score(candidate,old,_palace_mask(candidate),masks,size_m,scope)
        if score is None:
            raise ValueError("Расположение слишком близко к предыдущему варианту")
        candidate.update(input_seed=seed,source=label)
        pool.append((score,candidate,spec))
        return score

    def best_result(stop):
        best=max(pool,key=lambda item:item[0])
        neural=[entry for entry in pool if entry[1]["source"]=="architecture_qwen" and entry[0]>=best[0]-.055]
        if neural:
            best=max(neural,key=lambda item:item[0])
        return dict(best[1],search={
            "budget_s":budget,"elapsed_s":round(time.monotonic()-started,2),
            "procedural_drafts":procedural,"valid_recipes":len(pool),"ai_passes":local_completed,
            "selected":best[1]["source"],"score":best[0],"stop":stop,"trace":list(notes),
        })

    def publish():
        nonlocal published
        if not checkpoint:
            return
        candidate=best_result("in_progress")
        key=(candidate["seed"],candidate["source"])
        if published!=key:
            checkpoint(candidate)
            published=key

    def vary(spec,school):
        nonlocal procedural
        procedural+=1
        try:
            accept(spec,"architecture_rules",school)
        except ValueError as error:
            if not pool and len(notes)<4:
                notes.append({"phase":"layout","error":str(error)})

    progress("Обзор · опоры, разрез и тип потолка")
    breadth,rounds,iterations,cap={
        60:(24,2,1,25),
        600:(48,22,16,32),
        3600:(96,110,75,45),
    }[budget]
    schools=tuple(PALACE_PROFILES)
    axes=[(wall,ceiling) for wall in ARCH_WALLS for ceiling in ARCH_CEILINGS]
    rng.shuffle(axes)
    for index in range(breadth):
        if (pool and finish()) or time.monotonic()>=deadline:
            break
        spec=_hall_random_spec(rng)
        spec["walls"],spec["ceiling"]=axes[index%len(axes)]
        vary(spec,explicit_style or rng.choice(schools))
        if len(pool)==1 and published is None:
            publish()
    if not pool:
        raise ValueError("Не найден допустимый эскиз "+str(notes[:2]))
    publish()

    inference=None
    if backend=="native" and not finish() and time.monotonic()<deadline:
        try:
            inference=_palace_native_files()
        except (ValueError,RuntimeError,OSError) as error:
            notes.append({"phase":"model","error":str(error)})
    stop="rules_only" if backend=="rules" else "model_unavailable" if not inference else "completed_passes"
    for step_index in range(max(iterations,rounds if inference else 0)):
        if finish() or time.monotonic()>=deadline:
            break
        remaining=deadline-time.monotonic()
        structure=step_index<max(2,rounds//3)
        phase="structure" if structure else "detail"
        label="Композиция" if structure else "Проработка"
        progress(f"{label} · {step_index+1} · {len(pool)} схем · до {math.ceil(remaining)} с")
        shortlist=sorted(pool,key=lambda item:item[0],reverse=True)[:3]
        if step_index<iterations:
            for j,(_,ref,original) in enumerate(shortlist):
                if finish() or time.monotonic()>=deadline:
                    break
                variation=dict(original)
                if structure:
                    axis=("section","walls","ceiling","layout")[(step_index+j)%4]
                    variation[axis]=_hall_random_spec(rng)[axis]
                else:
                    variation.update(reach=round(max(.35,min(1.,original["reach"]+rng.uniform(-.15,.15))),2),
                                     growth=round(max(.8,min(1.3,original["growth"]+rng.uniform(-.16,.16))),2),
                                     motif=rng.choice(("shell","sunburst","vine","flower")))
                vary(variation,ref["style"])
            publish()
        remaining=deadline-time.monotonic()
        if not inference or step_index>=rounds or remaining<4 or finish():
            continue
        axis=("walls","ceiling","layout","section")[step_index%4]
        top=shortlist[0][2]
        exclude=(axis,top[axis]) if step_index and structure else None
        context={"target":scope,"hall_m":size_m,"base":[{"draft":entry[2],"score":entry[0]} for entry in shortlist],
                 "avoid_recent":[item.get("architecture",{}) for item in old[-5:]],
                 "recent":[item.get("architecture") for item in notes[-4:] if item.get("architecture")],
                 "replace":exclude,
                 "task":("Propose a different silhouette and distribution of the bays." if structure else
                         "Improve focal hierarchy, ornamental scale and relief. Keep the stronger structural features.")}
        if scope=="portal":
            context["task"]="Design only the relief above a door. Use motif and growth to express the request; reach is its width. Ignore the rest of the hall."
        note={"phase":phase,"local_model":"Qwen3 8B"}
        t=time.monotonic()
        try:
            spec=_hall_local_model(*inference,"Qwen3 8B",prompt or "Выразительный непохожий барочный зал.",
                                   context,remaining-1,seed+step_index,cap,exclude,finish)
            signature=tuple(spec[key] for key in ("walls","ceiling","section","layout","bays","order","motif","reach","growth"))
            note.update(architecture={key:spec[key] for key in ("walls","ceiling","section","layout","bays")},
                        comment=spec["edit"])
            if signature in visited:
                raise ValueError("Модель повторила найденную композицию")
            visited.add(signature)
            note["score"]=accept(spec,"architecture_qwen",explicit_style or shortlist[0][1]["style"])
            local_completed+=1
        except (RuntimeError,OSError,KeyError,TypeError,ValueError,subprocess.SubprocessError) as error:
            note["error"]=str(error)[:380]
        note["seconds"]=round(time.monotonic()-t,2)
        notes.append(note)
        publish()
    if finish():
        stop="accepted_early"
    elif deadline-time.monotonic()<4:
        stop="time_budget"
    result=best_result(stop)
    if checkpoint:
        checkpoint(result)
    return result


def search_hall(prompt="",style="random",seed=None,previous=None,budget=60,history=(),
                progress=None,backend="native",size_m=None,finish=None,checkpoint=None,scope="hall",
                ensemble_seconds=None):
    """Use the same composition in every preset, then spend extra time on its geometry."""
    if budget not in HALL_BUDGETS:
        raise ValueError("Выберите 1, 10 или 60 минут")
    if ensemble_seconds is not None:
        if scope!="hall" or not 1<=ensemble_seconds<=3600:
            raise ValueError("Объёмная композиция доступна для целого зала с бюджетом 1–3600 секунд")
        finish=finish or (lambda:False)
        progress=progress or (lambda message:None)
        started=time.monotonic()
        base=_search_hall_baseline(prompt,style,seed,previous,60,history,progress,backend,
                                   size_m,finish,checkpoint,scope)
        progress("Сравнение объёмных рам и рельефа")
        result=search_ensemble(base,size_m or (12,8.5,6.8),time.monotonic()+ensemble_seconds,
                               progress,finish,checkpoint or (lambda plan:None))
        result["search"].update(ensemble_budget_s=ensemble_seconds,
                                elapsed_s=round(time.monotonic()-started,2),
                                stop="accepted_early" if finish() else ("ensemble_complete" if result.get("ensemble") else "ensemble_fallback"))
        if checkpoint:
            checkpoint(result)
        return result
    if budget==60:
        return _search_hall_baseline(prompt,style,seed,previous,budget,history,progress,backend,
                                     size_m,finish,checkpoint,scope)
    started=time.monotonic()
    finish=finish or (lambda:False)
    progress=progress or (lambda message:None)

    def emit(candidate):
        if checkpoint:
            report=dict(candidate["search"],budget_s=budget,elapsed_s=round(time.monotonic()-started,2),
                        stop="in_progress")
            checkpoint(dict(candidate,search=report))

    base=_search_hall_baseline(prompt,style,seed,previous,60,history,progress,backend,
                               size_m,finish,emit if checkpoint else None,scope)
    engine=None
    if backend=="native" and not finish() and base["search"]["stop"]!="model_unavailable":
        try:
            engine=_palace_native_files()
        except (OSError,ValueError,RuntimeError):
            pass

    def propose(instruction,brief,context,remaining,proposal_seed,schema):
        return _hall_json_response(*engine,"Qwen3 8B",instruction,brief,context,remaining,
                                   proposal_seed,35,schema,finish)

    return refine_hall(base,scope,size_m,budget,started,progress,finish,emit,
                       propose if engine else None,prompt)


def portal_checked(portal):
    if not isinstance(portal,dict) or type(portal.get("seed")) is not int:
        raise ValueError("Некорректный рецепт лепнины над дверью")
    plate=dict(id="p1",x=0,y=0,rx=.5,ry=.5,**{key:portal[key] for key in ("shape","motif","elements")})
    validate_hall_layout([plate])
    for key,low,high in (("width",.55,1.30),("relief",.60,1.45),("curl",0,1),("foliage",0,1)):
        value=portal.get(key)
        if type(value) not in (float,int) or not low<=value<=high:
            raise ValueError("Недопустимый параметр портала: "+key)
    result=dict(portal)
    if "refinement" in result:
        result["refinement"]=refinement_checked(result["refinement"],"portal")
    return result


def edit_hall_zone(plan,scope,prompt,*,checkpoint=None,**options):
    """Build a replacement recipe anchored to one architectural zone."""
    if scope not in ("ceiling","portal") or not (prompt or "").strip():
        raise ValueError("Выберите зону и введите описание правки")
    previous=plan.get("zones",{}).get("ceiling",plan) if scope=="ceiling" else plan
    history=[hall_history_item(previous)] if previous.get("architecture") else []
    # The patch and the existing room use the same material palette.
    def apply(candidate):
        if candidate["style"]!=plan["style"]:
            candidate=dict(candidate,style=plan["style"])
        zones=dict(plan.get("zones",{}))
        title="потолка" if scope=="ceiling" else "лепнины над дверью"
        if scope=="ceiling":
            zones[scope]=candidate
        else:
            text=prompt.lower()
            motifs=(("раков|ракуш","shell"),("розет|лучист|солнеч","sunburst"),
                    ("акант|лоз|виноград|ветв","vine"),("цвет|букет","flower"))
            motif=next((value for regex,value in motifs if re.search(regex,text)),None)
            motif=motif or candidate["layout"][0]["motif"]
            elements={"shell":["shell","beads","scroll"],"sunburst":["fan","rosette","scroll"],
                      "vine":["spray","scroll","rosette"],"flower":["rosette","spray","beads"]}[motif]
            compact=bool(re.search(r"сдерж|легк|лёгк|меньше|плоск|неглуб",text))
            arch=candidate["architecture"]
            zones[scope]=portal_checked({
                "shape":candidate["wall_shape"],"motif":motif,"elements":elements,
                "seed":candidate["seed"],"width":.68+.60*arch["reach"],
                "relief":.72 if compact else .88+.36*arch["reach"],
                "curl":candidate["curl"],"foliage":min(.28,candidate["foliage"]) if compact else candidate["foliage"],
                **({"refinement":candidate["refinement"]} if candidate.get("refinement") else {}),
            })
        return dict(plan,zones=zones,zone_edit={"target":scope,"prompt":prompt},
                    title=plan["title"].split(" · Правка ")[0]+" · Правка "+title,
                    search=candidate["search"])

    def save(candidate):
        if checkpoint:
            checkpoint(apply(candidate))

    candidate=search_hall(prompt,style=plan["style"],previous=previous,history=history,scope=scope,
                          checkpoint=save if checkpoint else None,**options)
    return apply(candidate)
