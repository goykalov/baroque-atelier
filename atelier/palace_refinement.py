"""Sequential, bounded relief passes over an already selected hall."""
import math
import random
import re
import subprocess
import time

REFINEMENT_LABELS = {
    "frames":"Резные окончания плафонов", "panels":"Лепные панно цоколя",
    "figures":"Скульптуры на консолях", "rims":"Многослойные рамы плафонов",
    "frieze":"Рельефный фриз стен", "figures_extra":"Скульптурные группы на боковых стенах",
    "portal":"Резные крылья над дверью", "portal_extra":"Вторая ступень рельефа над дверью",
}
REFINEMENT_PHASES = {
    "hall":("frames","panels","figures","rims","frieze","figures_extra"),
    "ceiling":("frames","rims"),
    "portal":("portal","portal_extra"),
}
REFINEMENT_MOTIFS = ("acanthus","shell","rosette","garland")


def refinement_checked(data, scope="hall"):
    if not isinstance(data,dict) or set(data)!={"version","stages"} or data["version"]!=1:
        raise ValueError("Некорректная версия проработки")
    passes=data["stages"]
    allowed=REFINEMENT_PHASES[scope]
    if not isinstance(passes,dict) or set(passes)-set(allowed):
        raise ValueError("Рельеф отнесён к неизвестной зоне")
    for stage in passes.values():
        if (not isinstance(stage,dict) or set(stage)!={"motif","count","projection","spread"}
                or stage["motif"] not in REFINEMENT_MOTIFS
                or type(stage["count"]) is not int or not 2<=stage["count"]<=6):
            raise ValueError("Некорректная геометрия проработки")
        for key in ("projection","spread"):
            value=stage[key]
            if type(value) not in (int,float) or not .35<=value<=1.:
                raise ValueError("Параметр проработки вышел за границы")
    return data


def refine_hall(base, scope, size_m, budget, started, progress, finish, checkpoint, propose, prompt):
    """Keep an accepted stage when subsequent proposals repeat or miss its footprint."""
    phases=REFINEMENT_PHASES[scope]
    light_count=3 if scope=="hall" else 1
    stages={}
    journal=[]
    deadline=started+budget
    compact=min((size_m or (12,8.5,6.8))[:2])<5.1
    text=(prompt or "").lower()
    plain=bool(re.search(r"(?:сдержанн|умеренн|л[её]гк|неглубок)\w*\s+(?:лепнин|рельеф)",text))
    no_figures=not base["dense"].get("figures",True) or bool(re.search(r"без\s+(?:скульптур|статуй|фигур)",text))
    no_carving=bool(re.search(r"без\s+(?:лепнины|орнамента|резьбы|декора)",text))
    preferred=next((motif for pattern,motif in (
        ("акант|ветв","acanthus"),("раков|ракуш","shell"),("розет|лучист","rosette"),("гирлянд","garland"),
    ) if re.search(pattern,text)),None)
    schema={"type":"object","properties":{
        "motif":{"type":"string","enum":list(REFINEMENT_MOTIFS)},
        "count":{"type":"integer","minimum":2,"maximum":6},
        "projection":{"type":"number","minimum":.35,"maximum":1.},
        "spread":{"type":"number","minimum":.35,"maximum":1.},
    },"required":["motif","count","projection","spread"],"additionalProperties":False}

    def result(stop):
        search=dict(base["search"],budget_s=budget,elapsed_s=round(time.monotonic()-started,2),stop=stop,
                    geometry_passes=len(stages),refinement_trace=list(journal))
        plan=dict(base,search=search)
        if stages:
            plan["refinement"]={"version":1,"stages":dict(stages)}
        return plan

    for index,kind in enumerate(phases if budget==3600 else phases[:light_count]):
        if finish() or time.monotonic()>=deadline:
            break
        if no_carving or (kind.startswith("figures") and no_figures):
            continue
        progress("Геометрия · "+REFINEMENT_LABELS[kind])
        target_count=3 if compact or plain else (4 if index<light_count else 5)
        target_depth=.49 if plain else (.67 if index<light_count else .84)
        target_spread=.58 if compact else (.69 if index<light_count else .78)
        rng=random.Random(base["seed"]+1153*(index+1))
        motif=preferred or rng.choice(REFINEMENT_MOTIFS)
        fallback={"motif":motif,"count":target_count,"projection":target_depth,"spread":target_spread}

        def rank(candidate):
            if (plain and candidate["projection"]>.65) or (compact and candidate["spread"]>.78):
                return -math.inf
            diversity=sum(item["motif"]==candidate["motif"] for key,item in stages.items()
                          if not key.startswith("figures"))
            return (1.-.12*abs(candidate["count"]-target_count)
                    -.55*abs(candidate["projection"]-target_depth)-.45*abs(candidate["spread"]-target_spread)
                    +.08*(preferred==candidate["motif"])-.05*diversity)

        best=fallback
        source="rules"
        seen=set()
        attempts=0
        instruction=("Design one real baroque relief layer within a fixed architectural room. "
                     "Choose a botanical motif, the number of repetitions, normalized relief projection "
                     "and spread across its reserved footprint. Preserve openings, existing paintings, "
                     "protected voids and main architecture. Return JSON matching the schema.")
        if propose:
            tries=2 if index<light_count else 3
            for attempt in range(tries):
                remaining=deadline-time.monotonic()
                if finish() or remaining<4:
                    break
                attempts+=1
                context={"pass":kind,"zone":scope,"room_m":size_m,"style":base["style"],
                         "architecture":base["architecture"],"saved":stages,"fitting_target":fallback,
                         "request":"Propose a shape variant" if not attempt else
                                   "Revise the current layer for clarity and avoid the previous alternative.",
                         "current":best,"previous_proposals":[list(key) for key in sorted(seen)]}
                try:
                    candidate=propose(instruction,prompt,context,remaining-1,base["seed"]+37*index+attempt,schema)
                    refinement_checked({"version":1,"stages":{kind:candidate}},scope)
                except (RuntimeError,ValueError,TypeError,KeyError,OSError,subprocess.SubprocessError):
                    continue
                key=tuple(candidate[k] for k in ("motif","count","projection","spread"))
                if key in seen:
                    break
                seen.add(key)
                if rank(candidate)>=rank(best)-(.16 if source=="rules" else 0):
                    best,source=candidate,"qwen"
                if rank(best)==-math.inf:
                    best,source=fallback,"rules"
        if finish() or time.monotonic()>=deadline:
            break
        stages[kind]=best
        journal.append({"stage":kind,"source":source,"proposals":attempts,"alternatives":len(seen),
                        "elapsed_s":round(time.monotonic()-started,2)})
        checkpoint(result("in_progress"))
    stop="accepted_early" if finish() else "time_budget" if time.monotonic()>=deadline else "completed_refinement"
    final=result(stop)
    checkpoint(final)
    return final


def refinement_stage(plan, kind):
    return plan.get("refinement",{}).get("stages",{}).get(kind)


def _refinement_geometry():
    if "_PalacePanel" in globals():
        return _PalacePanel, panel_outline, sprout, _enrich_bays
    from palace_ornament import _PalacePanel as panel_type, panel_outline as outline
    from palace_branching import sprout as branch
    from palace_enrichment import _enrich_bays as bays_for
    return panel_type, outline, branch, bays_for


def _refinement_spray(panel, branch, x, y, angle, length, stage, seed, depth, layer=3):
    motif=stage["motif"]
    rise=length*.12*stage["projection"]
    if motif=="shell":
        panel.scallop(x,y,angle,length*.54,panel.light)
    elif motif=="rosette":
        panel.rosette(x,y,length*.27,stage["count"]+3,angle,panel.light)
    else:
        panel.pearl(x,y,rise,length*.12,panel.trim)
    for side in (-1,1):
        theta=angle+side*.70+(math.pi if side<0 else 0)
        panel.scroll(x,y,theta,length*.72,side,panel.d>=2)
        for k in range(stage["count"]):
            t=(k+1)/(stage["count"]+1)
            u=x+math.cos(theta)*length*t*.62
            v=y+math.sin(theta)*length*t*.62
            panel.leaf(u,v,theta+side*.72,length*(.44-.18*t),length*.09,side*length*.09,
                       rise*(1-.36*t),panel.light,(k+side)%2==0)
        if motif in ("acanthus","garland"):
            bound=length*1.03
            branch(panel.geom,panel.zone,panel.frame,x,y,theta,length*.92,seed+side,
                   panel.style,panel.d,depth,depth=layer,spread=stage["spread"],
                   limit=(x-bound,y-bound,x+bound,y+bound),gild=panel.trim=="gold")


def add_refined_ceiling(roof, plan, size, detail, relief):
    panel_type,outline,branch,_=_refinement_geometry()
    length,width,height=size
    cove=min(height*.115,.075*min(length,width))
    a,b=length/2-cove,width/2-cove
    for index,field in enumerate(plan["layout"]):
        rx,ry=field["rx"]*a,field["ry"]*b
        section=min(rx,ry)
        if section<155:
            continue
        def frame(x,y,z):
            return field["x"]*a+x,-field["y"]*b-y,height-z
        for kind in ("frames","rims"):
            stage=refinement_stage(plan,kind)
            if not stage:
                continue
            deep=kind=="rims"
            zone="Плафон "+field["id"]+" · "+REFINEMENT_LABELS[kind]
            seed=plan["seed"]+127*index+int(deep)*1231
            depth=min(2.,relief*(.83+.58*stage["projection"]))
            panel=panel_type(roof,zone,frame,1000,1000,plan["style"],detail,depth,seed,plan)
            ring=[(.93*rx*x,.93*ry*y) for x,y in (outline(field["shape"],i/96) for i in range(96))]
            if deep:
                ridge=min(24.,section*.035)*stage["projection"]
                for scale,z in ((1.004,14.),(.98,24.)):
                    panel.tube(panel.light,[(x*scale,y*scale,z) for x,y in ring],ridge,.70,True)
                for i in range(0,96,max(2,10-stage["count"])):
                    x,y=ring[i]
                    if i%3==0 and stage["motif"]=="rosette":
                        panel.rosette(x*.993,y*.993,ridge*1.15,6,i/96,panel.trim)
                    else:
                        panel.pearl(x*.993,y*.993,31.,max(4.,ridge*.63),panel.trim)
            else:
                for side in (-1,1):
                    for pair in (-1,1):
                        x,y=.57*rx*side,.63*ry*pair
                        size=min(section*.24,151.)*(.75+.25*stage["spread"])
                        _refinement_spray(panel,branch,x,y,math.atan2(y,x)+math.pi/2,size,stage,seed+13*side+pair,depth)
    rims=refinement_stage(plan,"rims")
    if rims:
        _refine_ceiling_flanks(roof,plan,(a,b,height),detail,relief,rims,panel_type,branch)


def _refine_ceiling_flanks(roof, plan, envelope, detail, relief, stage, panel_type, branch):
    """Reserve whole relief footprints beside the paintings before carving any of them."""
    a,b,height=envelope
    boxes=[(p["x"]*a,p["y"]*b,p["rx"]*a,p["ry"]*b) for p in plan["layout"]]
    text=plan.get("prompt","").lower()
    corners=bool(re.search(r"(?:угл\w*[^.!]{0,28}(?:пуст|чист|свобод)|(?:свобод|пуст|чист)\w*\s+угл)",text))
    center=bool(re.search(r"(?:центр\w*[^.!]{0,20}(?:пуст|чист|свобод)|(?:свобод|пуст|чист)\w*\s+центр)",text))
    accepted=[]
    for x,y,rx,ry in sorted(boxes,key=lambda box:-(box[2]*box[3])):
        radius=min(350.,.48*min(rx,ry))*(.78+.22*stage["spread"])
        if radius<130.:
            continue
        for sign in (-1,1):
            u=x+sign*(rx+radius+60.)
            if abs(u)+radius>.88*a or abs(y)+radius>.88*b:
                continue
            if corners and abs(u)+radius>.62*a and abs(y)+radius>.62*b:
                continue
            if center and abs(u)-radius<.20*a and abs(y)-radius<.20*b:
                continue
            if any(abs(u-px)<radius+qx+32 and abs(y-py)<radius+qy+32 for px,py,qx,qy in boxes):
                continue
            if any(math.hypot(u-px,y-py)<radius+r+42 for px,py,r in accepted):
                continue
            accepted.append((u,y,radius))
        if len(accepted)>=stage["count"]+1:
            break
    zone="Плафон · Акантовые композиции между полями"
    seed=plan["seed"]+9351
    depth=min(2.,relief*(.96+.5*stage["projection"]))
    for index,(x,y,radius) in enumerate(accepted):
        def frame(u,v,z):
            return x+u,-y-v,height-z
        panel=panel_type(roof,zone,frame,1000,1000,plan["style"],detail,depth,seed+index,plan)
        axis=.32*math.copysign(1.,x)
        panel.scallop(0,0,axis,radius*.64,panel.light)
        for fan in range(4):
            heading=axis+fan*math.pi/2
            branch(roof,zone,frame,0,0,heading,radius*.91,seed+17*index+fan,plan["style"],detail,depth,
                   depth=4,spread=stage["spread"],limit=(-radius,-radius,radius,radius),gild=panel.trim=="gold")
            panel.leaf(0.,0.,heading,radius*.49,radius*.13,radius*.12,12.,panel.main)


def add_refined_walls(g, plan, size, detail, relief, frames):
    panel_type,_,branch,bays_for=_refinement_geometry()
    length,width,height=size
    scale=min(height/4900,min(length,width)/6200,1.45)
    for wall,(name,span,frame) in enumerate(frames):
        if wall==0:
            continue
        bays=list(bays_for(plan,wall,span,scale,size))
        for index,(x,bay) in enumerate(bays):
            if wall==3 and index==len(bays)//2:
                continue
            for kind,level in (("panels",.107),("frieze",.833)):
                stage=refinement_stage(plan,kind)
                if not stage:
                    continue
                zone=name+" · "+REFINEMENT_LABELS[kind]
                depth=min(2.,relief*(.81+.58*stage["projection"]))
                seed=plan["seed"]+181*wall+71*index+int(kind=="frieze")*877
                panel=panel_type(g,zone,frame,1000,1000,plan["style"],detail,depth,seed,plan)
                y=height*level
                high=kind=="frieze"
                span=min(bay*.21,height*(.052 if high else .038))*(stage["spread"]*.46+.51)
                points=[(x+bay*.31*(2*k/32-1),y+height*.014*math.sin(math.pi*k/32),30*scale)
                        for k in range(33)]
                panel.tube(panel.light,points,8*scale,.68)
                if high:
                    panel.scallop(x,y+.013*height,math.pi*.5,min(span*.82,bay*.14),panel.light)
                for side in (-1,1):
                    _refinement_spray(panel,branch,x+side*bay*.12,y,side*.33,span,stage,seed+side,depth)


def add_refined_portal(g, portal, frame, x, y, width, height, style, detail, relief, recipe):
    panel_type,_,branch,_=_refinement_geometry()
    for kind in ("portal","portal_extra"):
        stage=refinement_stage(portal,kind)
        if not stage:
            continue
        deep=kind=="portal_extra"
        depth=min(2.,relief*(.85+.58*stage["projection"]))
        seed=portal["seed"]+int(deep)*981
        panel=panel_type(g,"Портал · лепнина над дверью",frame,1000,1000,style,detail,depth,seed,recipe)
        amplitude=min(width*.17,height*.21)*(.70+.30*stage["spread"])
        for side in (-1,1):
            _refinement_spray(panel,branch,x+side*width*(.19 if deep else .30),
                              y+height*(.16 if deep else -.15),side*.52,amplitude,stage,seed+side,depth,
                              layer=4 if deep else 3)
