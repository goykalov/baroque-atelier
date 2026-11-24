"""Architecture inside an unchanged room envelope, in millimetres."""
import math
import random
import re
from array import array


ARCH_WALLS=("arcade","pilasters","alcoves","gallery","canopy","grotto")
ARCH_CEILINGS=("star","rib_vault","garlands","woven","shells","cassettes")
ARCH_LABELS={"arcade":"аркада","pilasters":"парные колонны","alcoves":"экседры",
             "gallery":"верхняя галерея","canopy":"балдахины","grotto":"гротески",
             "star":"лучистое переплетение","rib_vault":"ребристый свод","garlands":"гирлянды",
             "woven":"плетёный свод","shells":"веерные раковины","cassettes":"глубокие кессоны"}


def _architecture_imports():
    if "_room_frame" in globals():
        return globals()
    import palace_room
    import palace_enrichment
    import palace_ornament
    import palace_branching
    return {**vars(palace_room),**vars(palace_enrichment),**vars(palace_ornament),**vars(palace_branching)}


def _architecture_ring(g, mat, zone, f, x, y, z, radial, levels, flutes=0, twist=0):
    ns=48 if flutes else 24
    rows=[]
    lo,hi=levels[0][0],levels[-1][0]
    for h,r in levels:
        row=[]
        for j in range(ns):
            a=2*math.pi*j/ns
            # Keep winding in the height axis positive for the capped ring mesh.
            rr=radial*r*(1+.085*math.cos(flutes*a+twist*(h-lo)/max(1,hi-lo))) if flutes else radial*r
            row.append((x+rr*math.cos(a),y+h,z-rr*math.sin(a)))
        rows.append(row)
    _architecture_imports()["_room_sweep"](g,mat,zone,f,rows)


def _architecture_column(g,zone,f,x,z,height,radius,kind):
    r=radius
    _architecture_ring(g,"plaster",zone,f,x,0,z,r,[(0,1.55),(.21*r,1.55),(.38*r,1.42),(.55*r,1.25),(r,1.15)])
    _architecture_ring(g,"gold",zone,f,x,.8*r,z,r,[(0,1.16),(.21*r,1.23),(.42*r,1.05)])
    levels=[(r+(height-2.8*r)*j/24,1+.10*math.sin(math.pi*j/24)-.23*j/24) for j in range(25)]
    twist=math.tau*2.8 if kind=="twist" else 0
    _architecture_ring(g,"plaster",zone,f,x,0,z,r,levels,12,twist)
    _architecture_ring(g,"gold",zone,f,x,height-1.95*r,z,r,
                       [(0,.78),(.24*r,.90),(.51*r,.94),(.75*r,1.24),(1.15*r,1.13),(1.25*r,1.49),(1.69*r,1.49),(1.95*r,1.55)])


def _architecture_wall(g,plan,size,detail,relief,frames,rng):
    ctx=_architecture_imports()
    draw_box, mould, bays_for=ctx["_room_box"],ctx["_room_mould"],ctx["_enrich_bays"]
    panel_class, offset, sprout=ctx["_PalacePanel"],ctx["_room_offset"],ctx["sprout"]
    L,W,H=size; arch=plan["architecture"]; style=plan["style"]
    s=min(H/4900,min(L,W)/6200,1.45)
    reach=arch["reach"]; hand=arch["asymmetry"]
    kind=arch["walls"]
    material="plaster" if style=="bavarian" else "gold"
    recipe={k:plan[k] for k in ("curl","foliage","gilding")}
    recipe.update(plan.get("zone_tuning",{}).get("wall",{}))

    for i,(label,span,f) in enumerate(frames):
        # Window wall remains unobstructed. A feature can frame the entrance without crossing its aperture.
        if i==0:continue
        if kind=="gallery" and i==3:continue
        bays=list(bays_for(plan,i,span,s,size))
        gallery_height=H*(.57+.032*reach)
        if kind=="gallery":
            zone=label+" · верхняя галерея"
            z=min(630*s,span*.12)
            draw_box(g,"shadow",zone,f,-span*.47,span*.47,gallery_height-72*s,gallery_height+4*s,4*s,z)
            for h,w,colour in ((0,25,"plaster"),(24,9,"gold"),(178,12,"gold"),(197,24,"plaster")):
                mould(g,colour,zone,f,[(-span*.47,gallery_height+h*s,z),(span*.47,gallery_height+h*s,z)],w*s,15*s)
            n=max(10,min(50,round(span/(195*s))))
            for j in range(n+1):
                x=span*.94*(j/n-.5)
                _architecture_ring(g,"gold" if j%3==0 else "plaster",zone,f,x,gallery_height+18*s,z,
                                   24*s,[(0,.8),(23*s,.96),(54*s,.55),(86*s,1.1),(115*s,.68),(163*s,.81)])
        for j,(x,wide) in enumerate(bays):
            portal=i==3 and j==len(bays)//2
            if portal and kind in ("alcoves","canopy","grotto"):continue
            zone=label+" · "+ARCH_LABELS[kind]+" "+str(j+1)
            bay_width=wide*(.89 if portal else .73)
            richness=max(.25,recipe["foliage"])
            salt=rng.randrange(2**31)
            if kind in ("arcade","pilasters","gallery"):
                top=gallery_height-52*s if kind=="gallery" else H*(.66 if portal else .62+.075*reach)
                depth=min(450*s,.13*wide)*(.52+.48*reach)
                radius=min(118*s,bay_width*.09)
                for side in (-1,1):
                    x1=x+side*bay_width*.5
                    _architecture_column(g,zone,f,x1,depth,top,radius,"twist" if kind=="pilasters" else "fluted")
                    if kind=="pilasters" and wide>1200*s and not portal:
                        _architecture_column(g,zone,f,x1-side*2.38*radius,depth*.62,top*.96,radius*.72,"fluted")
                if kind=="arcade" and not portal:
                    for r,adj,c in ((.94,25,"shadow"),(1.,29,"plaster"),(1.07,12,"gold"),(1.12,7,"plaster")):
                        line=[(x+.5*bay_width*r*math.cos(math.pi*k/48),
                               top+min(.5*bay_width,H*.13)*r*math.sin(math.pi*k/48),depth+adj*s)
                              for k in range(49)]
                        mould(g,c,zone,f,line,adj*s,adj*s)
                elif kind=="pilasters" and not portal:
                    for height,thick,c in ((0,34,"plaster"),(35,14,"gold"),(59,19,"plaster")):
                        mould(g,c,zone,f,[(x-bay_width*.56,top+height*s,depth),
                                           (x+bay_width*.56,top+height*s,depth)],thick*s,thick*s)
            elif kind=="alcoves":
                # Inset arch shell projects onto the room side of the existing wall.
                lo, spring=H*.22,H*(.60+.04*reach)
                rx,ry=bay_width*.45,min(H*.148,bay_width*.49)
                z=min(480*s,.18*wide)
                for side in (-1,1):
                    draw_box(g,"plaster",zone,f,x+side*rx-50*s,x+side*rx+50*s,lo,spring,0,z)
                for j1 in range(11):
                    u0,u1=math.pi*j1/11,math.pi*(j1+1)/11
                    _architecture_imports()["_room_sweep"](g,material,zone,f,
                        [[(x+(rx*rr)*math.cos(t),spring+(ry*rr)*math.sin(t),dep)
                           for rr,dep in ((.72,15*s),(.89,z*.86),(1.0,z),(1.12,42*s))]
                         for t in (u0,u1)])
                draw_box(g,"gold",zone,f,x-rx*1.14,x+rx*1.14,lo-45*s,lo,0,z*.88)
            elif kind in ("canopy","grotto"):
                ax=min(wide*.39,720*s); ay=H*(.50+.05*reach)
                span_y=H*(.21+.04*reach)
                projection=min(440*s,.16*wide)
                for k in range(3+(arch["order"]>=5)):
                    phase=(k-1.5)*.15*hand
                    path=[]
                    for t in range(55):
                        v=t/54
                        wave=(math.sin(v*math.pi*3.3+phase)*.14*hand if kind=="grotto" else 0)
                        path.append((x+ax*(2*v-1)*(1+k*.06),
                                     ay+span_y*(math.sin(math.pi*v)*(.7+k*.08)+wave),
                                     projection*(.28+.63*math.sin(math.pi*v))*(1-k*.13)))
                    mould(g,material if k%2 else "plaster",zone,f,path,max(16*s,(51-8*k)*s),22*s)
                if detail>=2 and richness>.29:
                    for side in (-1,1):
                        origin=x+side*ax*.75
                        sprout(g,zone,offset(f,0,0,projection*.30),origin,ay+60*s,
                               math.pi/2+side*.32,span_y*.58,salt+side,style,2,relief,
                               depth=min(4,arch["order"]),spread=.67+hand*.38,
                               limit=(x-wide*.46,H*.34,x+wide*.46,H*.81))


def _architecture_subdivide(vertices, faces, max_edge):
    """Split long panel edges with one shared midpoint per edge."""
    max_sq=max_edge**2
    points=[tuple(vertices[i:i+3]) for i in range(0,len(vertices),3)]
    triangles=[tuple(faces[i:i+3]) for i in range(0,len(faces),3)]

    def length_sq(a,b):
        p,q=points[a],points[b]
        return (p[0]-q[0])**2+(p[1]-q[1])**2

    while True:
        midpoints={}

        def midpoint(a,b):
            key=(a,b) if a<b else (b,a)
            if key not in midpoints and length_sq(a,b)>max_sq:
                midpoints[key]=len(points)
                points.append(tuple((p+q)*.5 for p,q in zip(points[a],points[b])))
            return midpoints.get(key)

        split=[]
        for a,b,c in triangles:
            m,n,p=midpoint(a,b),midpoint(b,c),midpoint(c,a)
            count=sum(i is not None for i in (m,n,p))
            if count==1:
                if m is None:
                    a,b,c,m,n,p=(b,c,a,n,p,m) if n is not None else (c,a,b,p,m,n)
                split.extend(((a,m,c),(m,b,c)))
            elif count==2:
                if m is None:
                    a,b,c,m,n,p=b,c,a,n,p,m
                elif n is None:
                    a,b,c,m,n,p=c,a,b,p,m,n
                split.append((m,b,n))
                if length_sq(a,n)<length_sq(m,c):
                    split.extend(((a,m,n),(a,n,c)))
                else:
                    split.extend(((a,m,c),(m,n,c)))
            elif count==3:
                split.extend(((a,m,p),(m,b,n),(p,n,c),(m,n,p)))
            else:
                split.append((a,b,c))
        if not midpoints:
            return array("f",(x for point in points for x in point)),array("i",(x for face in split for x in face))
        triangles=split


def _architecture_ceiling(g,plan,size,detail,relief,painted):
    ctx=_architecture_imports()
    model=ctx["_room_frame"]((0,0,size[2]),(1,0,0),(0,-1,0),(0,0,-1))
    mould=ctx["_room_mould"]
    L,W,H=size; a,b=L/2,W/2
    spec=plan["architecture"]; name=spec["ceiling"]
    n,q,skew=spec["order"],spec["reach"],spec["asymmetry"]
    drop=min(H*.175,b*.24,680.)*q
    ceiling_zone="Потолок · "+ARCH_LABELS[name]
    def elevation(x,y):
        u,v=x/a,y/b
        border=max(0,min(1,(1-max(abs(u),abs(v)))/.17))
        if name=="star":
            radius=math.hypot(u,v)
            ray_weight=1-math.exp(-(radius/.26)**2)
            h=.28*(1+math.cos(5.4*radius))*(.86+.14*ray_weight*math.cos(2*n*math.atan2(v,u)))
        elif name=="rib_vault":
            h=abs(v)**2.5*.84+.10*u*u
        elif name=="garlands":
            h=.22+.44*abs(math.cos(n*u*math.pi/2+skew*.4))*abs(v)**1.04
        elif name=="woven":
            h=.24+.36*abs(math.sin(n*(u+.69*v)*math.pi/4+skew*.60)*math.cos(n*(v-.35*u)*math.pi/4))
        elif name=="shells":
            h=.10+.73*max(abs(u),abs(v))*(.34+.66*math.sin(n*math.atan2(v,u))**2)
        else:
            cell=(math.sin(n*math.pi*u/2)*math.sin((n-1)*math.pi*v/2))**2
            h=.10+.77*cell*(2-cell)
        return drop*h*border

    # The slab, contours, leaf blades and paintings follow one height field.
    # At the envelope the height field returns to zero, keeping the wall joins and outside size fixed.
    del g.parts[("Плафон","body")]
    vs=[]
    grid=max(64,math.ceil(max(L,W)/125))
    xy=[(a*(2*i/grid-1),b*(2*j/grid-1)) for i in range(grid+1) for j in range(grid+1)]
    heights=[elevation(x,y) for x,y in xy]
    quad=lambda i,j:i*(grid+1)+j

    def slab_height(x,y):
        # The same diagonal as the slab's indexed triangles. Boundaries follow its exact profile.
        u=max(0.,min(float(grid),(x/a+1)*grid/2))
        v=max(0.,min(float(grid),(y/b+1)*grid/2))
        i,j=min(grid-1,int(u)),min(grid-1,int(v))
        s,t=u-i,v-j
        base=heights[quad(i,j)]
        diagonal=heights[quad(i+1,j+1)]
        if t<=s:
            return (1-s)*base+(s-t)*heights[quad(i+1,j)]+t*diagonal
        return (1-t)*base+(t-s)*heights[quad(i,j+1)]+s*diagonal

    for layer in (0,1):
        vs.extend(model(x,y,heights[i] if layer==0 else -100) for i,(x,y) in enumerate(xy))
    count=(grid+1)**2
    fs=[]
    for i in range(grid):
        for j in range(grid):
            ids=(quad(i,j),quad(i+1,j),quad(i+1,j+1),quad(i,j+1))
            fs.extend((ids,tuple(k+count for k in reversed(ids))))
    border=[quad(i,0) for i in range(grid)]+[quad(grid,j) for j in range(grid)]+[quad(i,grid) for i in range(grid,0,-1)]+[quad(0,j) for j in range(grid,0,-1)]
    for i,j in zip(border,border[1:]+border[:1]):
        fs.append((j,i,i+count,j+count))
    g.mesh("body",ceiling_zone,vs,fs)
    for (zone,mat),(v,f) in g.parts.items():
        if (zone.startswith("Плафон") or zone.startswith("Потолок")) and mat!="body":
            mount=mat.startswith("fresco") or mat=="ground"
            if mount:
                v,f=_architecture_subdivide(v,f,max_edge=98.)
                g.parts[(zone,mat)]=v,f
            for k in range(0,len(v),3):
                # Small offset clears interpolation error where a paint triangle straddles a slab diagonal.
                v[k+2]-=slab_height(v[k],-v[k+1])+(5. if mount else 0.)
    # Deep ribs separate painted areas. Their inner paths move from one composition to the next.
    R=min(H*.115,min(a,b)*.15)
    boxes=[(p["x"]*(a-R),p["y"]*(b-R),p["rx"]*(a-R),p["ry"]*(b-R)) for p in plan["layout"]]
    text=str(plan.get("prompt","")).lower()
    protect_center=bool(re.search(r"(?:пуст|свобод|чист)\w*[^.!]{0,16}(?:центр|серед)|(?:центр|серед)\w*[^.!]{0,25}(?:пуст|свобод|чист)",text))
    protect_corners=bool(re.search(r"(?:пуст|свобод|чист)\w*[^.!]{0,16}угл|угл\w*[^.!]{0,25}(?:пуст|свобод|чист)",text))
    def clear(x,y):
        if protect_center and abs(x)<.19*a and abs(y)<.19*b:return False
        if protect_corners and abs(x)>.61*a and abs(y)>.61*b:return False
        return all(abs(x-x0)>rx*.92+55 or abs(y-y0)>ry*.92+55 for x0,y0,rx,ry in boxes)
    for k in range(-n,n+1):
        if k==0 and name!="woven":continue
        path=[]; spans=[]
        for i in range(101):
            t=i/100
            if name=="rib_vault":
                x=a*(k/(n+.8)+skew*.04*math.sin(math.pi*t)); y=b*(t-.5)*1.87
            elif name in ("shells","star"):
                angle=math.pi*k/n+skew*.10*t; radius=.27+.66*t
                if name=="star":angle+=.19*math.sin(math.pi*t)
                x=a*radius*math.cos(angle); y=b*radius*math.sin(angle)
            else:
                x=a*(t-.5)*1.89; y=b*(k/(n+.7)+.13*math.sin(n*.61*math.pi*t+k*.44)*q)
            if abs(x)<a*.96 and abs(y)<b*.96 and clear(x,y):
                path.append((x,y,slab_height(x,y)+13))
            elif path:
                if len(path)>=5:spans.append(path)
                path=[]
        if len(path)>=5:spans.append(path)
        for line in spans:
            mould(g,"plaster",ceiling_zone,model,line,26+16*q,18+11*q)
            mould(g,"gold",ceiling_zone,model,[(x,y,z+17) for x,y,z in line],10+4*q,8)


def build_architecture(g,plan,size,detail,relief,frames,painted=None):
    spec=plan["architecture"]
    if spec["walls"] not in ARCH_WALLS or spec["ceiling"] not in ARCH_CEILINGS:
        raise ValueError("Неизвестная пространственная композиция")
    _architecture_wall(g,plan,size,detail,relief,frames,random.Random(plan["seed"] ^ 279))
    _architecture_ceiling(g,plan,size,detail,relief,painted)
