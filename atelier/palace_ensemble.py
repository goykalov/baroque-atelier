"""Search and geometry for a ceiling-led interior with connected, large-scale relief."""
from array import array
import math
import random
import re
import time

ENSEMBLE_FAMILIES=("axial","transverse","quatrefoil")
ENSEMBLE_LABELS={"axial":"Продольный плафон","transverse":"Поперечный плафон","quatrefoil":"Четырёхлопастный плафон"}


def ensemble_checked(data):
    ranges={"reach":(.33,.70),"crown":(.20,.68),"drop":(.12,.23),"relief":(.55,1.),"branch":(.48,.94)}
    if (not isinstance(data,dict) or set(data)!=set(ranges)|{"family","wings","volutes","bays"}
            or data["family"] not in ENSEMBLE_FAMILIES
            or data["wings"] not in (2,4) or data["volutes"] not in (8,10,12,14)
            or type(data["bays"]) is not int or not 3<=data["bays"]<=5):
        raise ValueError("Некорректная композиция большого плафона")
    for name,(low,high) in ranges.items():
        value=data[name]
        if type(value) not in (int,float) or not low<=value<=high:
            raise ValueError("Недопустимая пропорция плафона: "+name)
    return dict(data)


def _ensemble_intent():
    if "_palace_expectations" in globals():
        return _palace_expectations,_palace_check_intent,_palace_clear_corners
    from palace_plan import _palace_expectations as expectations
    from palace_plan import _palace_check_intent as check, _palace_clear_corners as clear_corners
    return expectations,check,clear_corners


def ensemble_plan(base,spec):
    """Compose important fields before constructing the relief that connects them."""
    spec=ensemble_checked(spec)
    expectations,check,_=_ensemble_intent()
    _,empty,_=expectations(base.get("prompt",""))
    if empty:
        raise ValueError("Большой центральный плафон несовместим с пустым центром")
    family=spec["family"]
    a,b={
        "axial":(.46+.24*spec["reach"],.39+.20*spec["crown"]),
        "transverse":(.40+.18*spec["crown"],.51+.20*spec["reach"]),
        "quatrefoil":(.46+.18*spec["reach"],.45+.14*spec["crown"]),
    }[family]
    layout=[{"id":"p1","x":0.,"y":0.,"rx":a,"ry":b,
             "shape":"oval" if family=="transverse" else "lobed",
             "motif":"sunburst","elements":["scroll","spray","rosette"]}]
    if spec["wings"]==4 or family!="transverse":
        for sign in (-1,1):
            x=sign*(a+.96)/2
            layout.append({"id":f"p{len(layout)+1}","x":x,"y":0.,"rx":(.96-a)*.34,"ry":.30,
                           "shape":"oval","motif":"shell","elements":["shell","scroll","spray"]})
    if spec["wings"]==4 or family=="transverse":
        for sign in (-1,1):
            y=sign*(b+.96)/2
            layout.append({"id":f"p{len(layout)+1}","x":0.,"y":y,"rx":.26,"ry":(.96-b)*.34,
                           "shape":"lobed","motif":"flower","elements":["scroll","rosette","spray"]})
    prompt=base.get("prompt","")
    check({"layout":layout},prompt)
    # The example programme keeps the same palette and wall rhythm, and builds pilasters as requested.
    text=prompt.lower()
    columns="колонн" in text and not re.search(r"без\s+(?:парн\w*\s+)?колонн",text)
    walls="pilasters" if columns else base["architecture"]["walls"]
    architecture=dict(base["architecture"],walls=walls,section="vertical")
    old_paintings=list(base.get("paintings",{}).values())
    paintings={"p1":old_paintings[0]} if old_paintings else {}
    if len(old_paintings)>1:
        paintings.update({p["id"]:art for p,art in zip(layout[1:],old_paintings[1:])})
    zones={key:value for key,value in base.get("zones",{}).items() if key!="ceiling"}
    program=dict(base["program"],wall_bays=spec["bays"])
    return dict(base,title=ENSEMBLE_LABELS[family],architecture=architecture,layout=layout,
                wall_bays=spec["bays"],program=program,
                paintings=paintings,pattern=family,ensemble=spec,zones=zones)


class _EnsembleSample:
    """Small mesh sink used to measure the relief geometry before assembling a full room."""
    def __init__(self):
        self.coords=array("f")

    def mesh(self, material, zone, vertices, faces):
        self.coords.extend(value for point in vertices for value in point)


def _ensemble_geometry():
    if "_PalacePanel" in globals():
        return _PalacePanel, panel_outline, sprout
    from palace_ornament import _PalacePanel as panel_type, panel_outline as outline
    from palace_branching import sprout as branch
    return panel_type,outline,branch


def add_ensemble_ceiling(roof, plan, size, detail, relief, preview=False):
    """Carve sweeping rails and successive fans around a shared central painting."""
    panel_type,outline,branch=_ensemble_geometry()
    length,width,height=size
    cove=min(height*.115,.075*min(length,width))
    a,b=length/2-cove,width/2-cove
    spec=plan["ensemble"]
    field=plan["layout"][0]
    rx,ry=field["rx"]*a,field["ry"]*b
    zone="Плафон · Пространственная резная рама"
    seed=plan["seed"]+952

    def frame(x,y,z):
        return x,-y,height-z

    panel=panel_type(roof,zone,frame,1000,1000,plan["style"],detail,relief,seed,plan)
    steps=48 if preview else 192
    d=spec["relief"]
    # A tall cross-section with carved returns and gold lines catches light at room scale.
    for k,(scale,r,z,material) in enumerate((
        (.903,41.,34.,"shadow"),(.914,49.,60.,"plaster"),(.936,36.,86.,"gold"),
        (.955,46.,121.,"plaster"),(.978,21.,140.,"gold"),(.993,23.,113.,"plaster"),
    )):
        radius=r*(.75+.45*d)
        path=[(x*rx*scale,y*ry*scale,z*d) for x,y in
              (outline(field["shape"],i/steps) for i in range(steps))]
        panel.tube(material,path,radius,.78,True,sides=6 if preview else 12)
        if k==4 and not preview:
            for i,(x,y,z) in enumerate(path[::3]):
                panel.pearl(x,y,z+18.,7.+d*4.,panel.light)
    count=spec["volutes"]
    for index in range(count):
        t=(index+.5)/count
        u,v=outline(field["shape"],t)
        nx,ny=outline(field["shape"],t+.004)
        tangent=math.atan2((ny-v)*ry,(nx-u)*rx)
        x,y=u*rx*.994,v*ry*.994
        span=min(610.,.32*min(rx,ry))*(.73+.27*spec["branch"])
        # Keep entire relief away from the corners and preserve the adjacent fields.
        if abs(x)+span>.66*a and abs(y)+span>.66*b:
            continue
        if any(abs(x-f["x"]*a)<f["rx"]*a+span*.67 and abs(y-f["y"]*b)<f["ry"]*b+span*.67
               for f in plan["layout"][1:]):
            continue
        panel.scallop(x,y,tangent,span*.58,panel.light)
        for hand in (-1,1):
            theta=tangent+(math.pi if hand<0 else 0)+.40*hand
            panel.scroll(x,y,theta,span*.78,hand,not preview)
            if preview:
                continue
            branch(roof,zone,frame,x,y,theta,span,seed+index*31+hand,plan["style"],detail,relief,
                   depth=4,spread=spec["branch"],limit=(x-span,y-span,x+span,y+span),gild=roof.gilded)
            for i in range(3):
                shift=span*(.15+.18*i)
                panel.leaf(x+shift*math.cos(theta),y+shift*math.sin(theta),theta+.78*hand,
                           span*(.58-.09*i),span*.125,span*.14*hand,65.-10*i,panel.light)


def _measure_ensemble(plan,size):
    sample=_EnsembleSample()
    add_ensemble_ceiling(sample,plan,size,detail=1,relief=1.,preview=True)
    length,width,height=size
    projected=set()
    deep=set()
    corners=set()
    for i in range(0,len(sample.coords),3):
        x,y,z=sample.coords[i:i+3]
        cell=(round(40*x/length),round(40*y/width))
        projected.add(cell)
        if height-z>=78:
            deep.add(cell)
        if min(abs(x)/(length*.5),abs(y)/(width*.5))>.65:
            corners.add(cell)
    main=plan["layout"][0]
    area=main["rx"]*main["ry"]
    depth=plan["ensemble"]["drop"]
    span=length/plan["wall_bays"]
    bay_fit=1.-min(1.,abs(span-2900.)/2100.)
    cove_fit=1.-min(1.,abs(depth-(.17 if height>4500. else .135))/.12)
    return {
        "relief_cells":len(projected),"deep_cells":len(deep),"corner_cells":len(corners),
        "focal_area":round(area,4),"bay_mm":round(span),"cove_drop_mm":round(height*depth),
        "score":round(.29*min(1.,len(projected)/180)+.25*min(1.,len(deep)/95)
                      +.25*(1.-min(1.,abs(area-.30)/.22))+.11*bay_fit+.10*cove_fit-.008*len(corners),6),
    }


def search_ensemble(base, size_m, end, progress, finish, publish):
    """Assess distinct carved compositions while time remains. Checkpoints stay usable."""
    size=tuple(value*1000 for value in size_m)
    rng=random.Random(base["seed"] ^ 871)
    seen=set()
    best=None
    score=-math.inf
    metrics={}
    trials=accepted=0
    trace=[]
    now=time.monotonic
    last=now()
    _,_,clear_corners=_ensemble_intent()
    corner_clear=clear_corners(base.get("prompt","").lower())

    def snapshot():
        search=dict(base.get("search",{}),ensemble_trials=trials,ensemble_valid=accepted,
                    ensemble_metrics=metrics,ensemble_improvements=list(trace))
        return dict(best or base,search=search)

    while not finish() and now()<end:
        spec={"family":rng.choice(ENSEMBLE_FAMILIES),"wings":rng.choice((2,4)),"bays":rng.randint(3,5),
              "volutes":rng.choice((8,10,12,14)),"reach":round(rng.uniform(.33,.70),2),
              "crown":round(rng.uniform(.20,.68),2),"drop":round(rng.uniform(.12,.23),2),
              "relief":round(rng.uniform(.55,1.),2),"branch":round(rng.uniform(.48,.94),2)}
        if best and rng.random()<.58:
            old=best["ensemble"]
            key=rng.choice(tuple(spec))
            spec=dict(old,**{key:spec[key]})
        key=tuple(spec.values())
        if key in seen:
            continue
        seen.add(key)
        trials+=1
        try:
            candidate=ensemble_plan(base,spec)
        except ValueError:
            if not best and trials>=60:
                break
            continue
        measure=_measure_ensemble(candidate,size)
        if corner_clear and measure["corner_cells"]:
            continue
        accepted+=1
        rating=measure["score"]
        if rating>score:
            best,score,metrics=candidate,rating,measure
            trace.append({"attempt":trials,"remaining_s":round(max(0.,end-now()),2),"score":rating})
            publish(snapshot())
        if now()-last>=12:
            progress(f"Объёмная композиция · {accepted} проверено · до {max(0,round(end-now()))} с")
            last=now()
    return snapshot()
