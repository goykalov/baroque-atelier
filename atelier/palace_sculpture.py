"""Place a public-domain sculpture on architectural brackets selected by the room."""
from array import array
import math
from pathlib import Path
import random
import struct

if "_enrich_bays" not in globals():
    from palace_enrichment import _enrich_bays, _enrich_offset, _enrich_profile
    from palace_refinement import refinement_stage


def _palace_putto_mesh():
    if "ghenv" in globals():
        folder=Path(ghenv.Component.OnPingDocument().FilePath).resolve().parent
    else:
        folder=Path(__file__).resolve().parent
    data=(folder/"palace_putto.bin").read_bytes()
    magic,vertex_count,face_count=struct.unpack_from("<4sII",data)
    end=12+vertex_count*12
    if magic!=b"PALA" or not vertex_count or len(data)!=end+face_count*12:
        raise ValueError("Повреждена комплектная сетка скульптуры")
    return array("f",data[12:end]),array("I",data[end:])


def place_palace_sculptures(g, plan, size, frames):
    """Fit seated figures to interior pedestals and a balanced pair above the door."""
    L,W,H=size
    scale=min(H/4900,min(L,W)/6200,1.45)
    rng=random.Random(plan["seed"] ^ 0xA17A027)
    verts,triangles=_palace_putto_mesh()
    style=plan["style"]
    body="gold" if style=="mexican" else "plaster"

    def place(frame,x,y,height,side,name,building_depth,stage=None):
        direction=side*rng.uniform(.11,.24)
        c,s=math.cos(direction),math.sin(direction)
        extent=height*.35
        f=_enrich_offset(frame,x,y,0)
        _enrich_profile(g,"shadow",name,f,extent*.82,-.055*height,.13*height,.58*height)
        _enrich_profile(g,"gold",name,f,extent,-.013*height,.034*height,.71*height)
        _enrich_profile(g,body,name,f,extent*.72,-.12*height,.17*height,.41*height)
        if stage:
            lift=stage["projection"]*.09*height
            _enrich_profile(g,body,name,f,extent*.92,-.15*height,.22*height,.62*height+lift)
            _enrich_profile(g,"gold",name,f,extent*.97,-.10*height,.05*height,.74*height+lift)
        oriented=[]
        for i in range(0,len(verts),3):
            u,v,d=verts[i]*side,verts[i+1],verts[i+2]
            oriented.append(frame(x+height*(c*u-s*d),y+height*v,building_depth+height*(s*u+c*d)))
        faces=((a,b,c) if side>0 else (a,c,b) for a,b,c in zip(triangles[::3],triangles[1::3],triangles[2::3]))
        g.mesh(body,name,oriented,faces)

    _,span,frame=frames[3]
    bays=list(_enrich_bays(plan,3,span,scale,size))
    x,bay=bays[len(bays)//2]
    for side in (-1,1):
        h=min(H*.088,bay*.206,660*scale)
        place(frame,x+side*.289*bay,H*.736,h,side,"Скульптура над порталом",h*.11)

    wall_index=rng.choice((1,2))
    _,span,frame=frames[wall_index]
    bays=list(_enrich_bays(plan,wall_index,span,scale,size))
    sorted_bays=sorted(bays,key=lambda b:b[1],reverse=True)
    original=sorted_bays[:rng.choice((1,2))]
    for j,(x,bay) in enumerate(original):
        h=min(H*.159,bay*.58,1150*scale)*rng.uniform(.89,1.)
        place(frame,x,H*.27,h,(-1)**j,"Скульптурный акцент "+str(j+1),h*.12)
    if not plan.get("refinement"):
        return
    candidates=[]
    for index in (3-wall_index,wall_index):
        label,span,frame=frames[index]
        for x,bay in _enrich_bays(plan,index,span,scale,size):
            if index!=wall_index or (x,bay) not in original:
                candidates.append((label,frame,x,bay))
    for kind,label in (("figures","Скульптурная консоль"),("figures_extra","Боковая скульптурная группа")):
        stage=refinement_stage(plan,kind)
        if not stage:
            continue
        count=min(3,stage["count"]-1,len(candidates))
        for j,(wall,frame,x,bay) in enumerate(candidates[:count]):
            h=min(H*.132,bay*.37,835*scale)*(.88+.12*stage["spread"])
            y=H*(.273 if kind=="figures" else .338)
            place(frame,x,y,h,(-1)**j,wall+" · "+label+" "+str(j+1),h*.15,stage)
        candidates=candidates[count:]
