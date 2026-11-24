"""Cast, carved frames and branching ornaments for the flat part of the ceiling."""

import bisect
import math
import random
import re

if "_PalacePanel" not in globals():
    from palace_ornament import _PalacePanel, panel_outline


def _dense_track(ring):
    spans = [0.]
    for i, (x, y) in enumerate(ring):
        nx, ny = ring[(i+1) % len(ring)]
        spans.append(spans[-1]+math.hypot(nx-x,ny-y))
    total = spans[-1]

    def point(s):
        s = (s%1)*total
        i = min(len(ring)-1,bisect.bisect_right(spans,s)-1)
        t = (s-spans[i])/(spans[i+1]-spans[i])
        x,y = ring[i]
        nx,ny = ring[(i+1)%len(ring)]
        return x+t*(nx-x),y+t*(ny-y)

    return total, point


def _dense_rim(panel, ring, phase, lobes, amplitude, rise):
    """Sweep contiguous, moulded rings so the projection reads as a carved frame."""
    edge, trim, background = panel.light, panel.trim, panel.main
    profile = (
        ((1.014,7),(1.006,31),(.980,47),(.956,39),(.949,20),(.952,6),background),
        ((.953,7),(.948,29),(.936,43),(.897,38),(.872,26),(.868,7),edge),
        ((.881,8),(.877,23),(.853,31),(.824,27),(.813,9),trim),
        ((.827,5),(.819,18),(.797,20),(.778,16),(.773,5),edge),
    )
    n = len(ring)
    for *section, mat in profile:
        vertices = []
        for j, (x, y) in enumerate(ring):
            axis = math.tau*j/n
            pulse = amplitude*(math.cos(lobes*axis+phase)+.33*math.sin((lobes+3)*axis-.8*phase))
            for radius, level in section:
                r = radius+pulse*(1.03-radius)
                z = level*rise*(.89+.12*math.cos(lobes*axis+phase))
                vertices.append((x*r,y*r,z))
        width = len(section)
        faces = []
        # Every course is an independently closed full ring.
        for i in range(n):
            base,next_base=i*width,((i+1)%n)*width
            for j in range(width):
                k=(j+1)%width
                faces.append((base+j,next_base+j,next_base+k,base+k))
        panel.emit(mat,vertices,faces)


def _dense_panel_carving(g, zone, frame, field, width, height, style, detail, relief,
                         recipe, spec, seed, painted, branch):
    panel=_PalacePanel(g,zone,frame,1000.,1000.,style,min(2,detail),relief,seed,recipe)
    rng=random.Random(seed)
    # These half extents correspond to the underlying field from decorate_panel().
    a,b=.448*width,.448*height
    S=min(a,b)
    if S < 155:
        return
    order=spec["order"]
    irregularity=spec["rhythm"]
    depth_scale=max(.28,min(1.24,S/640))
    ring=[(a*u,b*v) for u,v in (panel_outline(field["shape"],i/144) for i in range(144))]
    _dense_rim(panel,ring,rng.random()*math.tau,rng.choice((6,8,10)),.08+.13*irregularity,depth_scale)
    perimeter, track = _dense_track(ring)
    count=max(7,min(19,round(perimeter/(310+7*len(field["elements"])))))
    if detail==1:count=max(6,count//2)
    asymmetry=rng.uniform(.75,1)
    start=rng.random()/count
    motif=field["motif"]
    for i in range(count):
        t=start+(i+rng.uniform(-.28,.28)*irregularity)/count
        rx,ry=track(t)
        px,py=track(t+.008)
        tangent=math.atan2(py-ry,px-rx)
        length=min(235,perimeter/count*.40,S*.34) * spec["growth"]
        scales=1+.27*math.sin(i*2.39+asymmetry)+.10*rng.uniform(-1,1)
        root_x,root_y=.852*rx,.852*ry
        size=length*scales
        for hand in (-1,1):
            theta=tangent+(math.pi if hand<0 else 0)+hand*rng.uniform(.04,.28)*irregularity
            # Shape the raised leaf so it bridges two courses of the rim.
            panel.leaf(root_x,root_y,theta,size*.86,size*.24,hand*size*.13,28*depth_scale,panel.main)
            panel.leaf(root_x,root_y,theta+hand*.42,size*.62,size*.14,hand*size*.33,33*depth_scale,
                       panel.light,detail>1)
            if detail>1 and i%2:
                panel.leaf(root_x,root_y,theta-hand*.43,size*.72,size*.10,-hand*size*.21,31*depth_scale,
                           panel.trim,False)
        if i%3==0:
            x,y=.835*rx,.835*ry
            if motif in ("sunburst","flower"):
                panel.rosette(x,y,size*.37,rng.choice((5,7,9)),tangent,panel.light)
                panel.pearl(x,y,43*depth_scale,max(2.,size*.08),panel.trim)
            else:
                panel.scallop(x,y,tangent+(math.pi if i%2 else 0),size*.42,panel.main)
        elif (i+1)%3==0 and detail>1:
            panel.scroll(root_x,root_y,tangent+math.pi*(i%2),size*.65,(-1)**i,False)
        if branch and detail>1 and i%4==2:
            # Long curved stems follow the rim; explicit bounds keep them within their host field.
            inward=math.atan2(-root_y,-root_x)
            angle=tangent + .29*math.sin(inward-tangent)
            length=min(size*.64,S*.15)
            if length>=44:
                branch(
                    g,zone,frame,root_x,root_y,angle,length,seed+91*i,style,min(2,detail),relief,
                    depth=min(3,order),spread=.52,limit=(-a*.994,-b*.994,a*.994,b*.994),
                    gild=recipe["gilding"]>.36,
                )
    if painted:
        if branch and detail>1:
            # Give the painting several large, forked stems contained in its carved margin.
            for k in range(4+2*(order==4)):
                start=(k+rng.uniform(-.26,.26)*irregularity)/(4+2*(order==4))
                reach=min(820.,perimeter*.125,S*1.38)*spec["growth"]
                def rim_frame(u,v,z):
                    px,py=track(start+u/perimeter)
                    radial=1.-v/S
                    return frame(radial*px,radial*py,z)
                branch(g,zone,rim_frame,0.,S*.13,0.,reach,seed+1381*k,style,min(2,detail),relief,
                       depth=order,spread=.56,limit=(-S*.16,-S*.028,reach*1.08,S*.29),
                       gild=recipe["gilding"]>.36)
        return
    # Piercing, forked stems knit the outer wreath into the focal relief.
    for quadrant in range(4):
        t=quadrant/4+rng.uniform(-.065,.065)*irregularity
        rx,ry=track(t)
        x,y=.62*rx,.62*ry
        angle=math.atan2(-y,-x)
        if branch:
            span=min(740,math.hypot(x,y)*1.03)*spec["growth"]
            branch(g,zone,frame,x,y,angle,span,seed+571*quadrant,style,min(2,detail),relief,
                   depth=order if detail==3 else 3,spread=.66,limit=(-a*.79,-b*.79,a*.79,b*.79),
                   gild=recipe["gilding"]>.36)
        else:
            panel.scroll(x,y,angle,S*.29,(-1)**quadrant,True)
        if detail>1:
            panel.collar(x*.8,y*.8,min(117,S*.18),6 if field["shape"]=="octagon" else 10)
            panel.rosette(x*.8,y*.8,min(70,S*.105),rng.choice((7,9,11)),angle,panel.light)


def _dense_dist_polygon(x,y,ring):
    inside=False
    nearest=math.inf
    px,py=ring[-1]
    for nx,ny in ring:
        vx,vy=nx-px,ny-py
        den=vx*vx+vy*vy
        t=max(0.,min(1.,((x-px)*vx+(y-py)*vy)/den)) if den>1.e-8 else 0.
        nearest=min(nearest,(x-px-vx*t)**2+(y-py-vy*t)**2)
        if (py>y)!=(ny>y) and x<(nx-px)*(y-py)/(ny-py)+px:
            inside=not inside
        px,py=nx,ny
    return -math.sqrt(nearest) if inside else math.sqrt(nearest)


def _dense_excluded(plan):
    # Reserve zones requested in the same vocabulary as the plan validator.
    prompt=plan.get("prompt","").lower().replace("ё","е")
    clear_center=bool(re.search(
        r"(?:пуст\w*|свободн\w*)\s+(?:центр\w*|середин\w*)"
        r"|(?:центр\w*|середин\w*)\s+(?:(?:потолка|остав\w*)\s+){0,2}(?:пуст\w*|свободн\w*)",prompt))
    clear_corners=bool(re.search(
        r"(?:пуст\w*|свободн\w*|чист\w*)\s+(?:(?:четыре|все)\s+)?угл\w*"
        r"|угл\w*\s+(?:(?:потолка|комнаты|зала|остав\w*|будут|должны|быть|пусть)\s+){0,3}(?:пуст\w*|свободн\w*|чист\w*)"
        r"|(?:очист\w*|освободи\w*)\s+(?:все\s+)?угл\w*",prompt))
    return clear_center,clear_corners


def _dense_between_fields(g, frame, plan, a, b, detail, relief, recipe, spec, branch):
    rng=random.Random(plan["seed"]^0x0C0FFEE)
    style=plan["style"]
    clear_center,clear_corners=_dense_excluded(plan)
    ring_segments=44
    polygons=[]
    for f in plan["layout"]:
        ring=tuple(((f["x"]+.93*f["rx"]*u)*a,(f["y"]+.93*f["ry"]*v)*b)
                   for u,v in (panel_outline(f["shape"],j/ring_segments) for j in range(ring_segments)))
        polygons.append(ring)
    # Jitter the whole grid before packing flower cartouches. Clearance is measured from
    # the actual silhouette; the same seeds continue to work if the room dimensions change.
    limit=min(a,b)
    unit=min(1.5,max(.54,limit/2520))
    candidates=[]
    nx=max(10,min(22,round(a/(190*unit))))
    ny=max(8,min(19,round(b/(190*unit))))
    for i in range(nx):
        for j in range(ny):
            x=a*(2*(i+.5+rng.uniform(-.24,.24))/nx-1)*.91
            y=b*(2*(j+.5+rng.uniform(-.24,.24))/ny-1)*.91
            edge=min(.938*a-abs(x),.938*b-abs(y))
            if clear_center:
                edge=min(edge,math.hypot(max(0.,abs(x)-a*.21),max(0.,abs(y)-b*.21)))
            if clear_corners:
                edge=min(edge,math.hypot(max(0.,a*.62-abs(x)),max(0.,b*.62-abs(y))))
            if edge<82*unit:continue
            d=min(edge,min(_dense_dist_polygon(x,y,poly) for poly in polygons))
            if d>=82*unit:
                candidates.append((d*rng.uniform(.72,1.02),x,y,d))
    candidates.sort(reverse=True)
    anchors=[]
    for _,x,y,d in candidates:
        radius=min(d*.83,390*unit)*min(1.,spec["growth"])
        if any(math.hypot(x-u,y-v)<radius+r+22*unit for u,v,r in anchors):
            continue
        anchors.append((x,y,radius))
        if len(anchors) >= (11+4*detail):
            break
    zone="Плафон · резьба между полями"
    panel=_PalacePanel(g,zone,frame,1000.,1000.,style,
                       min(2,detail),relief,plan["seed"]+4419,recipe)
    for i,(x,y,radius) in enumerate(anchors):
        angle=rng.choice((0.,math.pi/2,math.pi,-math.pi/2))+rng.uniform(-.6,.6)*spec["rhythm"]
        r=radius
        aspect=rng.uniform(.56,.90)
        rotation=math.cos(angle),math.sin(angle)
        contour=[]
        for j in range(48):
            t=math.tau*j/48
            ellipse=(1+.112*math.cos(4*t))*r*.61
            u,v=ellipse*math.cos(t),ellipse*math.sin(t)*aspect
            co,si=rotation
            contour.append((x+co*u-si*v,y+si*u+co*v))
        for z,rim,width,mat in ((8,1.,.062,"shadow"),(16,1.,.050,panel.main),(19,.84,.037,panel.light)):
            panel.tube(mat,[(x+(u-x)*rim,y+(v-y)*rim,z) for u,v in contour],r*width,.52,True,sides=8)
        if i%3==1:
            panel.scallop(x,y,angle-math.pi/2,r*.40,panel.main)
        else:
            panel.rosette(x,y,r*.324,rng.choice((7,8,9,11)),angle,panel.light)
        if branch and detail>1 and r>=130*unit:
            for side in (-1,1):
                along=angle+(math.pi if side<0 else 0)
                sp=r*(.49+.14*rng.random())
                branch(g,zone,frame,x,y,along,sp,plan["seed"]+i*419+side,
                       style,min(2,detail),relief,depth=spec["order"],spread=.61,
                       limit=(x-r*.80,y-r*.80,x+r*.80,y+r*.80),gild=recipe["gilding"]>.36)
        else:
            for side in (-1,1):
                panel.scroll(x,y,angle+(math.pi if side<0 else 0),r*.66,side,detail>1)


def dense_ceiling(g,plan,size,detail,relief,painted_id=None):
    """Fit the carving to each field and spend the remaining area on spaced accents."""
    length,width,height=size
    cove=min(height*.115,.075*min(length,width))
    a,b=length/2-cove,width/2-cove
    spec={"growth":1.,"order":3,"rhythm":.55,**plan["dense"]}
    recipe={k:plan[k] for k in ("curl","foliage","gilding")}
    recipe.update(plan.get("zone_tuning",{}).get("ceiling",{}))
    branch=globals().get("sprout")
    if not branch:
        try:
            from palace_branching import sprout as branch
        except ImportError:
            # Low-detail crowns can still be generated when the standalone module
            # is only used by a mesh test harness.
            branch=None
    for i,field in enumerate(plan["layout"]):
        def frame(x,y,z):
            return x+field["x"]*a,-y-field["y"]*b,height-z
        _dense_panel_carving(g,"Плафон "+field["id"]+" · резная рама",frame,field,
                             2*field["rx"]*a,2*field["ry"]*b,plan["style"],detail,relief,
                             recipe,spec,plan["seed"]+1223*i,
                             field["id"] in painted_id if isinstance(painted_id,set) else field["id"]==painted_id,branch)
    _dense_between_fields(g,lambda x,y,z:(x,-y,height-z),plan,a,b,detail,relief,recipe,spec,branch)
