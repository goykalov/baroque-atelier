"""One-button local composition and a reproducible architectural specification."""
import math
import random
import re
import secrets
import time

if "_palace_compile" not in globals():
    from palace_plan import (
        PALACE_MOTIFS, PALACE_PROFILES, _palace_compile, _palace_content,
        _palace_inside, _palace_mask, _palace_similarity, default_plan, generate_best,
    )


def _ultra_school(prompt, style, rng):
    if style in PALACE_PROFILES:
        return style
    if style != "random":
        raise ValueError("Неизвестная школа барокко")
    for pattern, key in ((r"бавар|нимфенбург|амалиенбург|немецк", "bavarian"),
                         (r"русск|елизаветин|растрелли|екатерининск", "russian"),
                         (r"мексик|пуэбл|новоиспан|ретабло", "mexican")):
        if re.search(pattern,prompt.lower()):
            return key
    return rng.choice(tuple(PALACE_PROFILES))


def _ultra_random_draft(style, seed):
    rng=random.Random(seed)
    p=default_plan(style,seed)["program"]
    p["wall_bays"]=rng.choice((3,4,5))
    p["wall_rhythm"]=rng.choice(("alternating","processional","uniform"))
    p["axis"]=rng.choice(("x","y"))
    p["curl"]=round(rng.uniform(.58,.98),2)
    p["foliage"]=round(rng.uniform(.8,1),2)
    p["gilding"]=round(rng.uniform(.66,.95) if style!="bavarian" else rng.uniform(.44,.86),2)
    shapes={"bavarian":("lobed","arch","rect"),"russian":("rect","lobed","oval"),"mexican":("octagon","arch","rect")}[style]
    motifs=list(PALACE_MOTIFS);rng.shuffle(motifs)
    p["wall"]={"shape":rng.choice(shapes),"motif":motifs[3],"elements":["scroll","beads","spray","fan"]}
    for key,shape,motif in zip("ABC",shapes,motifs):
        p["palette"][key]={"shape":shape,"motif":motif,"elements":["scroll","spray","beads",rng.choice(("fan","rosette","shell"))]}
    # Build the two ends as reflected bands with a dominant larger field at the centre.
    def band(weight,n,main=False):
        centre=("A" if main else "B",rng.randint(2,4))
        if n==1:cells=[centre]
        elif n==2:cells=[("B",1),("B",1)]
        else:cells=[("C",rng_weight),(centre[0],centre[1]),("C",rng_weight)]
        return {"weight":weight,"cells":[{"weight":w,"type":t} for t,w in cells]}
    rng_weight=rng.randint(1,2)
    outer=band(rng.randint(1,3),rng.choice((1,2,3)))
    centre=band(rng.randint(4,8),rng.choice((1,3,3)),True)
    if rng.random()<.38:
        shoulder=band(rng.randint(1,2),rng.choice((1,2)))
        p["bands"]=[outer,shoulder,centre,shoulder,outer]
    else:
        p["bands"]=[outer,centre,outer]
    p["title"]=PALACE_PROFILES[style][0]+" · "+str(seed)
    return _palace_compile(p,style,seed,"procedural_random")


def _ultra_spec(plan, prompt, inherited=None):
    rng=random.Random(plan["seed"] ^ 0x56273)
    tune=dict(inherited) if inherited else {}
    text=prompt.lower().replace("ё","е")
    if "paint" not in tune:
        tune["paint"]=True
    if re.search(r"без\s+(?:фресок|фрески|росписи|живописи)|убр\w*\s+роспис",text):
        tune["paint"]=False
    elif re.search(r"фреск|роспис|живопис",text):
        tune["paint"]=True
    if not inherited or re.search(r"портал|колонн|капител",text):
        tune["capital"]=rng.choice(("acanthus","rosette","shell"))
        tune["pilaster"]=rng.choice(("fluted","tiered","ribbed"))
    if not inherited or re.search(r"лепнин|резьб|детал|орнамент",text):
        tune["tiers"]=rng.choice((2,3,3))
        tune["lace"]=rng.choice(("fan","spray","scroll"))
    if not inherited or re.search(r"золоч|позолот|золот",text):
        tune["gold"]=not bool(re.search(r"без\s+(?:золот|позолот)|убр\w*\s+позолот",text))
    return tune


def _dense_tuning(plan, prompt, previous):
    if previous and previous.get("dense"):
        settings=dict(previous["dense"])
    else:
        rng=random.Random(plan["seed"] ^ 0x7ECDA9A)
        settings={"growth":round(rng.uniform(.97,1.29),2),"order":rng.choice((3,4,4)),
                  "rhythm":round(rng.uniform(.31,.95),2)}
    text=prompt.lower().replace("ё","е")
    if re.search(r"хаот|нерегуляр|асимметр|дикий",text):settings["rhythm"]=.95
    if re.search(r"строг\w*\s+симметр|зеркальн\w*\s+симметр|равномерен",text):settings["rhythm"]=.18
    if re.search(r"пышн|гуще|насыщ|обильн\w*\s+(?:лепни|резьб)",text):settings["growth"]=1.29
    if re.search(r"(?:облегч|уменьш|меньш)\w*\s+(?:лепнин|резьб)",text):settings["growth"]=.8
    if re.search(r"без\s+(?:скульптур|статуй|фигур)",text):settings["figures"]=False
    elif re.search(r"добав\w*\s+(?:скульптур|стату|фигур)",text):settings["figures"]=True
    return settings


def new_ultra_plan(prompt="",style="random",seed=None,previous=None,backend="native",attempts=2,avoid=None,dense=False):
    """Create a decorated-room program from a prompt or a random seed."""
    prompt=(prompt or "").strip()
    seed=secrets.randbelow(2**30) if seed is None else int(seed)
    if not 1<=attempts<=4:raise ValueError("Число эскизов должно быть от 1 до 4")
    if backend not in ("native","rules"):raise ValueError("Выберите прямой запуск Qwen или автономные правила")
    started=time.monotonic()
    if style=="random" and previous:style=previous["style"]
    random_brief=not prompt or bool(re.fullmatch(
        r"(?:(?:сделай|создай|сгенерируй|любое|случайн\w*|пышн\w*|ультра|барокко|зал|комнату)[\s,!?.-]*)+",prompt.lower()))
    if previous and not prompt:
        raise ValueError("Введите правку для открытого проекта")
    if random_brief:
        drafts=[]
        records=[]
        last=(avoid or {}).get("plan",avoid)
        last_mask=_palace_mask(last) if last else None
        preferred=random.Random(seed ^ 718739).choice((3,5,7,9,11))
        for i in range(max(6,attempts*2)):
            trial=seed+7919*i
            school=_ultra_school(prompt,style,random.Random(trial))
            try:
                p=_ultra_random_draft(school,trial)
            except ValueError as exc:
                records.append({"seed":trial,"rejected":str(exc)})
                continue
            mask=_palace_mask(p)
            central=_palace_inside(max(p["layout"],key=lambda f:f["rx"]*f["ry"]),0,0)
            similarity=_palace_similarity(mask,last_mask) if last_mask else 0
            coverage=len(mask)/2401
            score=coverage+.12*central-.42*similarity+random.Random(trial^2641).random()*.19
            if dense:score-=.21*abs(len(p["layout"])-preferred)/8
            if last and _palace_content(p)==_palace_content(last):
                continue
            drafts.append((score,p))
            records.append({"seed":trial,"style":school,"fields":len(p["layout"]),"field_coverage":round(coverage,3),
                            "similarity":round(similarity,3),"score":round(score,4)})
        if not drafts:raise ValueError("Смените число варианта, чтобы подобрать подходящий эскиз")
        plan=max(drafts,key=lambda result:result[0])[1]
        plan["selection"]={"backend":"random","selected_seed":plan["seed"],"candidates":records,"seconds":round(time.monotonic()-started,2)}
        plan["prompt"]=prompt
    else:
        school=_ultra_school(prompt,style,random.Random(seed))
        plan=generate_best(prompt,school,seed,previous,attempts,backend)
    plan["ultra"]=_ultra_spec(plan,prompt,previous.get("ultra") if previous else None)
    if dense:plan["dense"]=_dense_tuning(plan,prompt,previous)
    plan["input_seed"]=seed
    return plan
