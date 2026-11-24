"""Small offline catalogue of public-domain ceiling paintings."""
from pathlib import Path
import random

PALACE_ART={
    "counsel":("Совет","fresco.jpg","https://www.nga.gov/artworks/241-study-ceiling-personification-counsel"),
    "monarchy":("Апофеоз испанской монархии","art/monarchy.jpg","https://www.metmuseum.org/art/collection/search/437791"),
    "planets":("Аллегория планет и континентов","art/planets.jpg","https://www.metmuseum.org/art/collection/search/437790"),
    "wealth":("Богатство испанской монархии","art/wealth.jpg","https://www.nga.gov/artworks/12137-wealth-and-benefits-spanish-monarchy-under-charles-iii"),
    "apollo":("Аполлон и искусства","art/apollo.jpg","https://www.nga.gov/artworks/132096-ceiling-apollo-presiding-over-military-and-historical-learning"),
}


def assign_palace_paintings(plan,count,previous=(),excluded=()):
    fields=[field for field in plan["layout"] if field["id"] not in excluded]
    count=min(count,len(PALACE_ART),len(fields))
    if count<=0 or not plan["ultra"]["paint"]:
        return {}
    rng=random.Random(plan["seed"] ^ 7391)
    unused=list(PALACE_ART)
    rng.shuffle(unused)
    avoided=set(previous)
    unused.sort(key=lambda k:k in avoided)
    ranked=sorted(fields,key=lambda p:p["rx"]*p["ry"]-.08*(p["x"]**2+p["y"]**2),reverse=True)
    result={}
    for p in ranked[:count]:
        def fit(key):
            # Prefer round compositions for round fields and the broad rectangular canvases for long fields.
            narrow=p["rx"]/max(.01,p["ry"])
            mismatch=(narrow>1.15 and key in ("monarchy","planets","wealth")) or (narrow<.75 and key in ("counsel","apollo"))
            return ((key in avoided),mismatch)
        choice=min(unused,key=fit)
        result[p["id"]]=choice
        unused.remove(choice)
    return result


def palace_art_paths(plan,root):
    root=Path(root)
    resolved={}
    ceiling=plan.get("zones",{}).get("ceiling",plan)
    for art in sorted(set(ceiling.get("paintings",{}).values())):
        if art not in PALACE_ART:
            raise ValueError("Неизвестная роспись в рецепте")
        path=root/PALACE_ART[art][1]
        if not path.is_file():
            raise ValueError("Нет локального изображения «"+PALACE_ART[art][0]+"»")
        resolved["fresco_"+art]=path
    return resolved


def palace_uv(key,u,v,width,height):
    if width>1.15*height and key in ("fresco_monarchy","fresco_planets","fresco_wealth"):
        return 1-v,u
    if height>1.22*width and key in ("fresco_counsel","fresco_apollo"):
        return v,1-u
    return u,v
