"""Room construction in millimetres, shared by Grasshopper and the OBJ exporter."""
import math
from array import array
if "decorate_panel" not in globals():
    from palace_ornament import decorate_panel, _PalacePanel
    from palace_refinement import add_refined_ceiling, add_refined_portal, add_refined_walls


ROOM_PALETTES = {
    "bavarian": {"body": (231, 221, 203), "plaster": (250, 239, 217), "ground": (180, 201, 194),
                 "accent": (194, 152, 145), "shadow": (150, 134, 111), "gold": (204, 156, 82)},
    "russian": {"body": (212, 227, 223), "plaster": (246, 237, 213), "ground": (154, 188, 187),
                "accent": (194, 156, 113), "shadow": (119, 108, 95), "gold": (201, 146, 53)},
    "mexican": {"body": (205, 179, 143), "plaster": (234, 208, 159), "ground": (123, 65, 52),
                "accent": (83, 116, 109), "shadow": (83, 52, 41), "gold": (204, 151, 66)},
}
for _pal in ROOM_PALETTES.values():
    _pal.update(wood=(124, 82, 52), oak=(153, 109, 69), walnut=(104, 70, 46), glass=(194, 216, 220),fresco=(227,214,191))


class RoomMeshes:
    """Compact indexed triangles, grouped by architectural part and material."""
    def __init__(self, gilded=True):
        self.parts = {}
        self.windows = []
        self.gilded=gilded

    def mesh(self, material, zone, vertices, faces):
        if material=="gold" and not self.gilded:material="plaster"
        key = (zone, material)
        if key not in self.parts:
            self.parts[key] = (array("f"), array("i"))
        coords, indices = self.parts[key]
        start = len(coords) // 3
        coords.extend(x for pt in vertices for x in pt)
        for face in faces:
            a, b, c = face[:3]
            indices.extend((a + start, b + start, c + start))
            if len(face) == 4:
                indices.extend((a + start, c + start, face[3] + start))


def _room_frame(origin, u, v, normal):
    def point(x, y, z):
        return tuple(origin[i] + x*u[i] + y*v[i] + z*normal[i] for i in range(3))
    return point


def _room_offset(frame, x, y, z=0):
    return lambda u, v, w: frame(x + u, y + v, z + w)


def _room_box(g, mat, zone, f, x0, x1, y0, y1, z0, z1):
    if min(x1-x0, y1-y0, z1-z0) <= .01:
        return
    pts = [f(x, y, z) for z in (z0,z1) for x,y in ((x0,y0),(x1,y0),(x1,y1),(x0,y1))]
    g.mesh(mat,zone,pts,[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])


def _room_sweep(g, mat, zone, frame, rows, loop=False):
    n = len(rows[0])
    pts = [frame(*p) for row in rows for p in row]
    faces = []
    for r in range(len(rows) if loop else len(rows)-1):
        a, b = r*n, ((r+1)%len(rows))*n
        for j in range(n):
            k = (j+1)%n
            faces.append((a+j,a+k,b+k,b+j))
    if not loop:
        for index in (0,len(rows)-1):
            row = rows[index]
            cap = len(pts)
            pts.append(frame(*(sum(p[i] for p in row)/n for i in range(3))))
            for j in range(n):
                a,b = index*n+j,index*n+(j+1)%n
                faces.append((cap,b,a) if index==0 else (cap,a,b))
    g.mesh(mat,zone,pts,faces)


def _room_mould(g, mat, zone, frame, path, r, depth, loop=False):
    # Oval cross section aligned with the path tangent.
    rows=[]
    for i,(x,y,z) in enumerate(path):
        a=path[i-1 if i or loop else 0]
        b=path[(i+1)%len(path) if loop else min(i+1,len(path)-1)]
        dx,dy=b[0]-a[0],b[1]-a[1]
        length=math.hypot(dx,dy) or 1
        row=[]
        for j in range(10):
            ang=j*math.tau/10
            w=r*math.cos(ang)
            row.append((x-dy/length*w,y+dx/length*w,z+depth*math.sin(ang)))
        rows.append(row)
    _room_sweep(g,mat,zone,frame,rows,loop)


def _room_cove(g,zone,frame,span,H,R,s,style):
    for i in range(16):
        t0=math.pi*.5*i/16
        t1=math.pi*.5*(i+1)/16
        d0,d1=(R*(1-math.cos(t)) for t in (t0,t1))
        h0,h1=(H-R+R*math.sin(t) for t in (t0,t1))
        rows=[[(u*(span/2-d),h,dd) for h,dd,d in
               ((h0,d0,d0),(h1,d1,d1),(h1+10,d1-10,d1),(h0+10,d0-10,d0))]
              for u in (-1,1)]
        _room_sweep(g,"body",zone,frame,rows)
    for t,w,mat in ((.04,17,"plaster"),(.12,7,"gold"),(.26,12,"plaster"),
                    (.95,6,"gold"),(1.27,12,"plaster"),(1.48,9,"gold")):
        d=R*(1-math.cos(t)); h=H-R+R*math.sin(t)
        _room_mould(g,mat,zone,frame,[(-span/2+d,h,d),(span/2-d,h,d)],w*s,w*s)
    # Dentils articulate the inner edge of the cornice.
    n=max(8,int(span/(95*s if style=="mexican" else 125*s)))
    step=(span-80*s)/n
    for j in range(n):
        x=-span/2+40*s+(j+.5)*step
        _room_box(g,"gold" if style!="bavarian" else "plaster",zone,frame,
                  x-step*.18,x+step*.18,H-R-39*s,H-R-16*s,5*s,27*s)


def _room_arch(g,zone,frame,x,span,H,s,scan):
    w=span*.35
    sill=H*.215
    crown=H*.795
    rise=min(w*.78,(crown-sill)*.27)
    spring=crown-rise
    n=24
    def edge(t):
        return x+w*math.cos(t),spring+rise*math.sin(t)
    pts=[edge(j*math.pi/n) for j in range(n+1)]
    for i in range(n):
        x1,y1=pts[i]; x0,y0=pts[i+1]
        # Solid masonry spandrel rises from the arch to the wall head.
        row=[(x0,y0),(x1,y1),(x1,H),(x0,H)]
        vs=[frame(u,v,z) for z in (-135*s,0) for u,v in row]
        g.mesh("body",zone,vs,[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
    a,b=x-span/2,x+span/2
    _room_box(g,"body",zone,frame,a,x-w,0,H,-135*s,0)
    _room_box(g,"body",zone,frame,x+w,b,0,H,-135*s,0)
    _room_box(g,"body",zone,frame,x-w,x+w,0,sill,-135*s,0)
    outline=[(x+w,sill),(x+w,spring)]+pts[1:]+[(x-w,sill)]
    # Single convex arch glazing, slightly recessed behind the mullions.
    rows=[[(u,v,z) for u,v in outline] for z in (-83*s,-76*s)]
    _room_sweep(g,"glass",zone,frame,rows)
    for mat,r in (("plaster",29),("gold",8)):
        path=[(u,v,(14 if mat=="plaster" else 40)*s) for u,v in outline]
        _room_mould(g,mat,zone,frame,path,r*s,(20 if mat=="plaster" else 5)*s,True)
    for j in (-1,0,1):
        u=w*j*.50
        top=spring+rise*math.sqrt(1-(u/w)**2)
        _room_box(g,"plaster",zone,frame,x+u-10*s,x+u+10*s,sill,top,-74*s,-47*s)
    for i in range(1,5):
        h=sill+(spring-sill)*i/4
        _room_box(g,"plaster",zone,frame,x-w,x+w,h-9*s,h+9*s,-75*s,-49*s)
    _room_box(g,"plaster",zone,frame,x-w-55*s,x+w+55*s,sill-43*s,sill+4*s,-56*s,70*s)
    if scan:
        g.windows.append((_room_offset(frame,x,(sill+crown)/2,23*s),2*w,crown-sill))


def _room_pier(g,zone,f,x,w,h,s,style,depth):
    lo=h*.205; hi=h*.815; width=min(w*.12,127*s)
    for y,scale,hh,mat in ((lo,1.25,75,"plaster"),(lo+85*s,1.01,22,"gold"),
                           (hi-85*s,1.02,31,"gold"),(hi-48*s,1.24,49,"plaster"),
                           (hi+8*s,1.40,20,"gold")):
        _room_box(g,mat,zone,f,x-width*scale,x+width*scale,y,y+hh*s,0,(35+18*scale)*s*depth)
    if style=="mexican":
        # An inverted taper and alternating blocks give the estípite its silhouette.
        levels=[(.00,.45),(.08,.65),(.13,.39),(.39,.89),(.46,1.02),(.51,.60),
                (.58,.86),(.65,.69),(.71,.95),(.77,.60),(.86,.72),(1.,1.05)]
        for j,((a,wa),(b,wb)) in enumerate(zip(levels,levels[1:])):
            rows=[]
            for t,dx in ((a,wa),(b,wb)):
                z=(39+45*dx)*s*depth
                y=lo+82*s+t*(hi-lo-156*s)
                rows.append([(x-width*dx,y,3*s),(x+width*dx,y,3*s),
                             (x+width*dx*.81,y,z),(x,y,z+14*s),(x-width*dx*.81,y,z)])
            _room_sweep(g,"gold" if j%3!=0 else "accent",zone,f,rows)
    else:
        _room_box(g,"plaster",zone,f,x-width*.86,x+width*.86,lo+65*s,hi-45*s,0,34*s*depth)
        count=5 if style=="russian" else 3
        for i in range(count):
            u=x+width*(i-(count-1)/2)*1.35/(count-1)
            _room_mould(g,"gold" if i in (0,count-1) else "plaster",zone,f,
                        [(u,lo+96*s,34*s*depth),(u,hi-70*s,34*s*depth)],
                        (8 if i in (0,count-1) else 11)*s,9*s*depth)
    for side in (-1,1):
        path=[]
        for i in range(42):
            t=i/41; angle=-math.pi*.45+t*math.tau*1.35
            rad=width*.56*(1-.89*t)
            path.append((x+side*(width*.53+rad*math.cos(angle)),hi-25*s+rad*math.sin(angle),64*s*depth))
        _room_mould(g,"gold",zone,f,path,9*s,8*s*depth)


def _room_floor(g,L,W):
    f=lambda x,y,z:(x,y,z)
    z="Паркет"
    _room_box(g,"walnut",z,f,-L/2,L/2,-W/2,W/2,-100,0)
    nx,ny=max(4,round(L/820)),max(4,round(W/820))
    for i in range(nx):
        for j in range(ny):
            x0,y0=-L/2+L*i/nx,-W/2+W*j/ny
            for k in range(5):
                a,b=(k/5,(k+1)/5) if (i+j)%2 else (0,1)
                c,d=(0,1) if (i+j)%2 else (k/5,(k+1)/5)
                mat=("wood","oak","wood","walnut","oak")[(k+i+2*j)%5]
                _room_box(g,mat,z,f,x0+a*L/nx+1,x0+b*L/nx-1,
                          y0+c*W/ny+1,y0+d*W/ny-1,0,4)


def build_palace(plan, size=(9000,6700,4900), detail=2, relief=1., foliage_delta=0., gilding_delta=0., window_asset=False, painting=True):
    L,W,H=(float(x) for x in size)
    if not (3400<=min(L,W)<=max(L,W)<=18000 and 2700<=H<=8000):
        raise ValueError("Размер зала должен быть 3,4–18 м по плану и 2,7–8 м по высоте")
    s=min(H/4900,min(L,W)/6200,1.45)
    ultra=plan.get("ultra")
    g=RoomMeshes(gilded=ultra is None or ultra["gold"]); style=plan["style"]
    zones=plan.get("zones",{})
    ceiling=zones.get("ceiling",plan)
    portal=zones.get("portal")
    ceiling_ultra=ceiling.get("ultra")
    roof=g if ceiling is plan else RoomMeshes(gilded=ceiling_ultra is None or ceiling_ultra["gold"])
    detail=max(1,min(3,int(detail)))
    depth=max(.35,min(2.,float(relief)))
    def tuning(zone, source):
        source_ultra=source.get("ultra")
        recipe={k:source[k] for k in ("curl","foliage","gilding")}
        recipe.update(source.get("zone_tuning",{}).get(zone,{}))
        recipe["foliage"]=max(0.,min(1.,recipe["foliage"]+foliage_delta))
        recipe["gilding"]=max(0.,min(1.,recipe["gilding"]+gilding_delta))
        if source_ultra:
            recipe["ultra"]=source_ultra
            if source_ultra["gold"]:
                recipe["gilding"]=max(.44 if style=="bavarian" else .63,recipe["gilding"])
        return recipe
    recipe=tuning("ceiling",ceiling)
    _room_floor(g,L,W)
    a,b=L/2,W/2
    R=min(H*.115,min(a,b)*.15)
    top=_room_frame((0,0,H),(1,0,0),(0,-1,0),(0,0,-1))
    _room_box(roof,"body","Плафон",top,-a,a,-b,b,-100,0)
    central=[p for p in ceiling["layout"] if abs(p["x"])<p["rx"] and abs(p["y"])<p["ry"]]
    paintings=painting if isinstance(painting,dict) else None
    painted=max(central,key=lambda p:p["rx"]*p["ry"]) if paintings is None and painting and central and (not ceiling_ultra or ceiling_ultra["paint"]) else None
    painted_ids=set(paintings or ())|({painted["id"]} if painted else set())
    for idx,p in enumerate(ceiling["layout"]):
        field=dict(recipe,**{k:p[k] for k in ("shape","motif","elements")})
        field["painted"]=p["id"] in painted_ids
        f=_room_offset(top,p["x"]*(a-R),p["y"]*(b-R),0)
        decorate_panel(roof,"Плафон "+p["id"],f,2*p["rx"]*(a-R),2*p["ry"]*(b-R),
                       style,detail,depth,ceiling["seed"]+idx*31,field)
        if paintings and p["id"] in paintings:
            zone="Плафон "+p["id"]
            roof.parts[(zone,"fresco_"+paintings[p["id"]])]=roof.parts.pop((zone,"fresco"))
    recipe=tuning("wall",plan)
    section=plan.get("architecture",{}).get("section")
    walls=[("Окна",L,(0,-b,0),(-1,0,0),(0,1,0)),("Восток",W,(a,0,0),(0,-1,0),(-1,0,0)),
           ("Зал",L,(0,b,0),(1,0,0),(0,-1,0)),("Портал",W,(-a,0,0),(0,1,0),(1,0,0))]
    frames=[]
    for i,(zone,span,origin,right,normal) in enumerate(walls):
        f=_room_frame(origin,right,(0,0,1),normal)
        frames.append((zone,span,f))
        n=plan["wall_bays"] if i%2==0 else max(2,round(plan["wall_bays"]*W/L))
        n=min(6,max(2,n),max(2,int(span/(850*s))))
        if i==3:
            n=max(3 if ultra else 1,n-1 if n%2==0 else n)
        weights=[1.]*n
        for j in range(n):
            if plan["wall_rhythm"]=="alternating": weights[j]=1+.14*math.cos(j*math.pi)
            if plan["wall_rhythm"]=="processional": weights[j]=1+.45*(1-abs(2*j-(n-1))/max(1,n-1))
        cursor=-span/2
        for j,v in enumerate(weights):
            bay=span*v/sum(weights); x=cursor+bay/2; end=cursor+bay
            sub=zone+" "+str(j+1)
            if i==0:
                _room_arch(g,sub,f,x,bay,H,s,window_asset)
                if ultra and detail>=2:
                    crest=_PalacePanel(g,sub,_room_offset(f,x,H*.805,26*s),1000,1000,style,
                                       min(2,detail),depth,plan["seed"]+j*43,recipe)
                    reach=min(bay*.19,235*s)
                    for hand in (-1,1):
                        angle=0 if hand>0 else math.pi
                        crest.scroll(hand*reach*.16,0,angle-hand*.57,reach,hand)
                        crest.leaf(hand*reach*.49,-reach*.09,angle-hand*.66,reach,.23*reach,
                                   hand*.21*reach,18*s,crest.main)
                    crest.focal(0,0,reach*.43,{"shell":"shell","fan":"sunburst","spray":"vine","scroll":"flower"}[ultra["lace"]])
            elif i==3 and j==n//2:
                door=min(.61*bay,1580*s); dh=H*.68
                _room_box(g,"body",sub,f,cursor,x-door/2,0,H,-135*s,0)
                _room_box(g,"body",sub,f,x+door/2,end,0,H,-135*s,0)
                _room_box(g,"body",sub,f,x-door/2,x+door/2,dh,H,-135*s,0)
                for hand in (-1,1):
                    mid=x+hand*door/4
                    _room_box(g,"wood",sub,f,mid-door/4+2,mid+door/4-2,0,dh,-70*s,-29*s)
                    for frac,hh in ((.26,.34),(.70,.41)):
                        dw=door*.189; dy=dh*hh/2; cy=dh*frac
                        path=[(mid+u*dw,cy+v*dy,-16*s) for u,v in ((-1,-1),(1,-1),(1,1),(-1,1))]
                        _room_mould(g,"gold",sub,f,path,14*s,8*s,True)
                for off in (-1,1):
                    _room_box(g,"plaster",sub,f,x+off*door/2-27*s,x+off*door/2+27*s,0,dh+60*s,0,50*s)
                _room_box(g,"gold",sub,f,x-door/2-56*s,x+door/2+56*s,dh,dh+46*s,0,67*s)
                if portal:
                    field=dict(recipe,**{key:portal[key] for key in ("shape","motif","elements","curl","foliage")})
                    panel_width=min(door*1.13*portal["width"],bay*.82)
                    panel_depth=max(.35,min(2., depth*portal["relief"]))
                    decorate_panel(g,"Портал · лепнина над дверью",_room_offset(f,x,H*.777),panel_width,H*.16,
                                   style,detail,panel_depth,portal["seed"],field)
                    if portal.get("refinement"):
                        add_refined_portal(g,portal,f,x,H*.777,panel_width,H*.16,style,detail,depth,field)
                else:
                    field=dict(recipe,shape="lobed",motif=plan["wall_motif"],elements=plan["wall_elements"])
                    panel_zone="Портал · лепнина над дверью" if section else sub
                    decorate_panel(g,panel_zone,_room_offset(f,x,H*.777),min(door*1.13,bay*.78),H*.16,
                                   style,detail,depth,plan["seed"]+900,field)
            else:
                _room_box(g,"body",sub,f,cursor,end,0,H,-135*s,0)
                field=dict(recipe,shape=plan["wall_shape"],motif=plan["wall_motif"],elements=plan["wall_elements"])
                feature=plan.get("architecture",{}).get("walls")
                prop={"alcoves":(.69,.48,.46),"gallery":(.83,.32,.34),"canopy":(.86,.43,.44),"grotto":(.84,.42,.40)}.get(feature,(.77,.57,.531))
                if section=="vertical":
                    prop=(prop[0]*.86,min(.58,prop[1]*1.15),max(.49,prop[2]))
                elif section=="tiered":
                    prop=(prop[0],prop[1]*.78,min(.38,prop[2]))
                elif section=="swept":
                    prop=(min(.90,prop[0]*1.10),prop[1]*.88,prop[2]+(.018 if j%2 else -.018))
                decorate_panel(g,sub,_room_offset(f,x,H*prop[2]),bay*prop[0],H*prop[1],
                               style,detail,depth,plan["seed"]+i*19+j%2,field)
            if i!=3 or j!=n//2:
                lo,hi=H*.042,H*.167
                path=[(x+u*bay*.388,lo if v<0 else hi,12*s) for u,v in ((-1,-1),(1,-1),(1,1),(-1,1))]
                _room_mould(g,"plaster",sub,f,path,17*s,12*s,True)
                _room_mould(g,"gold",sub,f,[(u,v,z+12*s) for u,v,z in path],4*s,4*s,True)
                for y,h,z,mat in ((H*.012,24,28,"plaster"),(H*.183,25,36,"plaster"),(H*.193,6,37,"gold")):
                    _room_box(g,mat,sub,f,cursor,end,y,y+h*s,0,z*s)
            # Festoons follow the architectural bay, linking the springing points and crest.
            if detail>=2 and recipe["foliage"]>.18:
                band=_PalacePanel(g,sub,_room_offset(f,x,H*.855,12*s),1120.,1000.,style,detail,depth,
                                  plan["seed"]+3*j,recipe)
                bw=bay*.42; hang=min(H*.060,bw*.34)
                for side in (-1,1):
                    def swag(t):
                        return side*(.08+.88*t)*bw,-hang*math.sin(math.pi*t)**.85
                    points=[(*swag(k/32),10*s) for k in range(33)]
                    band.tube(band.trim,points,6.5*s,.85)
                    for k in range(3+round(recipe["foliage"]*4)):
                        t=.11+k*.118
                        u,vv=swag(t);nx,ny=swag(t+.005);direction=math.atan2(ny-vv,nx-u)
                        for h in (-1,1):
                            band.leaf(u,vv,direction+h*.60,min(96*s,bw*.17),13*s,h*22*s,12*s,band.light)
                    u,vv=swag(.96)
                    band.scroll(u,vv,math.pi*.53 if side<0 else math.pi*.47,min(117*s,bw*.24),side)
                band.scallop(0,-hang*.31,0,min(114*s,bw*.26),band.main)
            if j: _room_pier(g,zone+" · пилястры",f,cursor,bay,H,s,style,depth)
            cursor=end
        _room_cove(g,zone+" · падуга",f,span,H,R,s,style)
    if ultra:
        if "enrich_room" in globals():enrich=globals()["enrich_room"]
        else:
            from palace_enrichment import enrich_room as enrich
        enrich(g,plan,(L,W,H),detail,depth,frames,roof=roof,ceiling=ceiling)
    elif roof is not g and ceiling_ultra and detail>=2:
        if "_enrich_ceiling" in globals():
            enrich_ceiling=globals()["_enrich_ceiling"]
        else:
            from palace_enrichment import _enrich_ceiling as enrich_ceiling
        enrich_ceiling(roof,ceiling,(L,W,H),detail,depth,s,R)
    if plan.get("dense") or ceiling.get("dense"):
        if "dense_walls" not in globals():
            from palace_dense_walls import dense_walls as add_walls
            from palace_dense_ceiling import dense_ceiling as add_ceiling
        else:
            add_walls,add_ceiling=dense_walls,dense_ceiling
        if plan.get("dense"):
            add_walls(g,plan,(L,W,H),detail,depth,frames)
        if ceiling.get("dense"):
            add_ceiling(roof,ceiling,(L,W,H),detail,depth,painted_ids)
        if detail>=2 and plan.get("dense") and plan["dense"].get("figures",True):
            if "place_palace_sculptures" in globals():statues=place_palace_sculptures
            else:
                from palace_sculpture import place_palace_sculptures as statues
            statues(g,plan,(L,W,H),frames)
    if plan.get("refinement"):
        add_refined_walls(g,plan,(L,W,H),detail,depth,frames)
    if ceiling.get("refinement"):
        add_refined_ceiling(roof,ceiling,(L,W,H),detail,depth)
    if plan.get("architecture") or ceiling.get("architecture"):
        if "build_architecture" in globals():architecture=build_architecture
        else:
            from palace_architecture import build_architecture as architecture
        architecture(g,plan,(L,W,H),detail,depth,frames,painted_ids,roof=roof,ceiling=ceiling)
    if roof is not g:
        g.parts.update(roof.parts)
    return g
