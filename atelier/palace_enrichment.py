"""Deep cornices and applied carving that follow the architecture of each generated hall."""

import math
import random
import re

if "_PalacePanel" not in globals():
    from palace_ornament import _PalacePanel


def _enrich_offset(frame, u, v, w=0):
    return lambda x, y, z: frame(u+x, v+y, w+z)


def _enrich_extrude(g, mat, zone, frame, half_span, profile):
    """Extrude a convex section parallel to the wall's horizontal axis."""
    n = len(profile)
    xyz = [frame(x, y, z) for x in (-half_span, half_span) for y, z in profile]
    faces = [(0, j+1, j) for j in range(1, n-1)]
    faces.extend((n, n+j, n+j+1) for j in range(1, n-1))
    for j in range(n):
        k = (j+1) % n
        faces.append((j, k, n+k, n+j))
    g.mesh(mat, zone, xyz, faces)


def _enrich_profile(g, mat, zone, frame, half_span, center, rise, projection):
    # A broad rear shoulder, two bevelled beads and a sloping front catch different light.
    profile = [(center+rise*y, projection*z) for y, z in
               ((-.50, -.04), (.50, -.04), (.50, .74), (.31, .99),
                (.12, 1.), (-.27, .88), (-.50, .62))]
    _enrich_extrude(g, mat, zone, frame, half_span, profile)


def _enrich_bays(plan, wall, span, scale, size):
    L,W,_ = size
    n = plan["wall_bays"] if wall%2==0 else max(2,round(plan["wall_bays"]*W/L))
    n = min(6,max(2,n),max(2,int(span/(850*scale))))
    if wall==3:
        n = max(3,n-(n%2==0))
    def weight(i):
        if plan["wall_rhythm"]=="alternating":
            return 1+.14*math.cos(i*math.pi)
        if plan["wall_rhythm"]=="processional":
            return 1+.45*(1-abs(2*i-(n-1))/max(1,n-1))
        return 1
    weights = [weight(i) for i in range(n)]
    x = -span/2
    for w in weights:
        bay = span*w/sum(weights)
        yield x+bay/2,bay
        x += bay


def _enrich_capital(g, zone, frame, x, y, half_width, scale, style, detail, relief, seed, recipe, crown):
    s = min(scale, half_width/125)
    local = _enrich_offset(frame,x,y,30*s)
    light, heavy = ("plaster", "gold") if style=="bavarian" else ("gold","plaster")
    for height, breadth, thickness, reach, mat in (
            (84,1.30,32,110,heavy),(101,1.40,16,118,light),
            (-74,.80,24,57,heavy),(-83,.79,13,60,light)):
        _enrich_profile(g,mat,zone,local,breadth*half_width,height*s,thickness*s,reach*s)
    panel = _PalacePanel(g,zone,local,1000,1000,style,min(detail,2),relief,seed,recipe)
    for tier in (0,1):
        count = 5 if tier==0 else 4
        for j in range(count):
            d = 2*j/(count-1)-1
            panel.leaf(half_width*.57*d, (-49+56*tier)*s, math.pi/2-d*.56,
                       (133-30*tier)*s,(29-5*tier)*s,d*22*s,(54+14*tier)*s,
                       light if tier==1 or abs(d)>.7 else heavy)
    for side in (-1,1):
        panel.scroll(side*half_width*.25,24*s,0 if side>0 else math.pi,
                     1.02*half_width,side,False)
        panel.pearl(side*half_width*.84,50*s,94*s,15*s,light)
    top = _PalacePanel(g,zone,_enrich_offset(local,0,0,86*s),1000,1000,
                       style,min(detail,2),relief,seed+93,recipe)
    if crown=="shell":
        top.scallop(0,11*s,0,51*s,light)
    elif crown=="rosette":
        top.rosette(0,32*s,50*s,8,0,light)
    else:
        top.leaf(0,-11*s,math.pi/2,86*s,21*s,9*s,11*s,light)
        top.rosette(0,30*s,27*s,6,0,heavy)


def _enrich_shaft(g, zone, frame, x, height, half_width, scale, style, shape):
    s=min(scale, half_width/125)
    span=height*.267
    y=height*.516
    # Rotate the extruded profiles into the vertical direction. Only the
    # original pier centreline is occupied, leaving each wall opening free.
    shaft=lambda u,v,w:frame(x-v,y+u,w+27*s)
    color="plaster" if style=="bavarian" else "gold"
    if shape=="tiered":
        for j in range(4):
            f=_enrich_offset(shaft,span*(-.75+.50*j),0)
            _enrich_profile(g,color,zone,f,span*.239,0.,half_width*(.9+.12*j),(42+9*j)*s)
            _enrich_profile(g,"plaster",zone,f,18*s,0.,half_width*1.42,84*s)
        return
    _enrich_profile(g,"plaster",zone,shaft,span,0.,1.31*half_width,62*s)
    count=7 if shape=="fluted" else 3
    for j in range(count):
        d=(2*j/(count-1)-1)
        _enrich_profile(g,color,zone,shaft,span-32*s,d*half_width*.55,
                        (9 if shape=="fluted" else 24)*s,(77-15*d*d)*s)


def _enrich_ceiling(g, plan, size, detail, relief, scale, cove):
    L,W,H=size
    s=scale
    a,b=L/2-cove,W/2-cove
    radius=min(a,b)*.13
    # This band occupies the gap between the edge of the fields' safe box
    # and the top of the cove. It never enters the central field coordinates.
    points=[]
    for j,(sx,sy) in enumerate(((1,1),(-1,1),(-1,-1),(1,-1))):
        for k in range(13):
            angle=(j+k/12)*math.pi/2
            points.append((sx*(a-radius)+(radius*math.cos(angle)),
                           sy*(b-radius)+(radius*math.sin(angle))))
    recipe={k:plan[k] for k in ("curl","foliage","gilding")}
    recipe.update(plan.get("zone_tuning",{}).get("ceiling",{}))
    if recipe["foliage"]<.13:
        return
    spec=plan["ultra"]
    style=plan["style"]
    seed=plan["seed"]
    local=lambda x,y,z:(x,-y,H-z)
    panel=_PalacePanel(g,"Плафон · резная падуга",local,1000,1000,style,
                       min(2,detail),relief,seed+972,recipe)
    color="plaster" if style=="bavarian" else "gold"
    for shift,rise,level,mat in ((0.,26,11,"shadow"),(.011,14,34,color),
                                (.022,7.6,43,"plaster"),(.049,16,14,color),
                                (.060,9.5,21,"plaster"),(.070,3.5,24,color)):
        loop=[(x*(1-shift),y*(1-shift),level*s) for x,y in points]
        panel.tube(mat,loop,rise*s,.65,True,12)
    raw=plan.get("prompt","").lower()
    clear=bool(re.search(
        r"(?:пуст\w*|свободн\w*|чист\w*)\s+(?:(?:четыре|все)\s+)?угл\w*"
        r"|угл\w*\s+(?:(?:потолка|комнаты|зала|остав\w*|будут|должны|быть|пусть)\s+){0,3}(?:пуст\w*|свободн\w*|чист\w*)"
        r"|(?:очист\w*|освободи\w*)\s+(?:все\s+)?угл\w*",raw))
    # Sprays run tangentially within the outer band. The curved corner
    # anchors have a different, larger fan, unless the request clears them.
    for axis in (0,1):
        u,v=(a,b) if axis==0 else (b,a)
        count=min(19,max(3,round(2*(u-radius)/(640*s))))
        for side in (-1,1):
            for j in range(count):
                advance=(2*(j+.5)/count-1)*(u-radius)
                x,y=(advance,.973*side*v) if axis==0 else (.973*side*v,advance)
                along=axis*math.pi/2
                if (j+seed)%3==1 and spec["lace"]!="scroll":
                    if spec["lace"]=="fan":
                        panel.scallop(x,y,along,58*s,color)
                    else:
                        panel.rosette(x,y,44*s,8,.17*j,color)
                else:
                    for hand in (-1,1):
                        panel.scroll(x,y,along+(math.pi if hand<0 else 0),138*s,
                                     side*hand,detail>=3 and abs(j-count/2)<3)
    if clear:
        return
    for sx in (-1,1):
        for sy in (-1,1):
            x=sx*(a-radius*.40)
            y=sy*(b-radius*.40)
            th=math.atan2(-sy,-sx)-math.pi/2
            span=min(223*s,radius*.59)
            panel.scallop(x,y,th,span,color)
            for side in (-1,1):
                panel.scroll(x,y,th+math.pi/2+side*.72,span*.90,side)


def _enrich_fascia(g, zone, frame, span, height, cove, scale, style, detail, relief, seed, recipe, bays):
    s = scale
    cornice = height-cove
    # The main quarter round behind this crown remains visible between its ribs.
    for y,h,d,mat in ((-194,29,35,"shadow"),(-175,18,66,"gold"),
                      (-147,37,85,"plaster"),(-110,36,108,"shadow"),
                      (-82,23,146,"gold"),(-56,42,164,"plaster"),
                      (-28,20,179,"gold"),(-7,18,161,"shadow"),
                      (13,33,138,"gold")):
        _enrich_profile(g,mat,zone,frame,span/2-40*s,cornice+y*s,h*s,d*s)
    for j,(x,width) in enumerate(bays):
        paint = "accent" if style!="russian" else "ground"
        center_y = cornice-119*s
        frieze = _PalacePanel(g,zone,_enrich_offset(frame,x,center_y,110*s),1000,1000,
                              style,1 if detail<3 else 2,relief,seed+j*83,recipe)
        M = min(188*s, .19*width)
        color = "plaster" if style=="bavarian" else "gold"
        # A shell or floral boss separates two curling branches in each bay.
        if (seed+j)%3==0 or style=="bavarian":
            frieze.scallop(0,0,0,M*.40,color)
        else:
            frieze.rosette(0,0,M*.24,6+(seed+j)%3,0,color)
        for side in (-1,1):
            direction = 0 if side>0 else math.pi
            frieze.scroll(side*M*.19,-7*s,direction-side*.18,M*1.19,-side)
            outer=min(width*.41,M*2.60)
            for k in range(3):
                r=M*(1.60+.21*k)
                if r >= outer:
                    break
                frieze.leaf(side*r,0,direction+side*(k*.19-.38),M*.46,M*.13,side*12*s,8*s,color,False)
        # Consoles at third points lend a structural rhythm to the frieze.
        for d in (-.35,.35):
            width_console=max(28*s,min(width*.06,83*s))
            mount=_enrich_offset(frame,x+d*width,cornice-77*s,0)
            _enrich_profile(g,paint,zone,mount,width_console,0,89*s,174*s)
            _enrich_profile(g,color,zone,mount,width_console,19*s,24*s,186*s)


def _enrich_base(g, zone, frame, bays, height, scale, style, detail, relief, seed, recipe, door):
    color="plaster" if style=="bavarian" else "gold"
    for j,(x,width) in enumerate(bays):
        if door and j==len(bays)//2:
            continue
        s=min(scale,width/1050)
        local=_enrich_offset(frame,x,height*.105,16*s)
        extent=min(width*.265,height*.122)
        panel=_PalacePanel(g,zone,local,1000,1000,style,min(2,detail),relief,seed+53*j,recipe)
        n=40
        for shift,mat in ((0,"shadow"),(7*s,color)):
            border=[((extent+shift)*math.cos(math.tau*i/n),
                     (71*s+shift)*math.sin(math.tau*i/n),8*s) for i in range(n)]
            panel.tube(mat,border,4.6*s,.8,True)
        if (seed+j)%2:
            panel.scallop(0,-27*s,0,60*s,color)
        else:
            panel.rosette(0,0,49*s,8,0,color)
        for side in (-1,1):
            panel.scroll(side*extent*.13,-5*s,0 if side>0 else math.pi,
                         min(.67*extent,210*s),-side)


def enrich_room(g, plan, size, detail, relief, frames):
    """Build small architectural projections over the existing wall mesh."""
    if detail < 2:
        return
    L,W,H = size
    s=min(H/4900,min(L,W)/6200,1.45)
    cove=min(H*.115,min(L,W)*.075)
    style=plan["style"]
    seed=plan["seed"]
    rng=random.Random(seed+9871)
    recipe={k:plan[k] for k in ("curl","foliage","gilding")}
    recipe.update(plan.get("zone_tuning",{}).get("wall",{}))
    _enrich_ceiling(g,plan,size,detail,relief,s,cove)
    if recipe["foliage"] < .13:
        return
    for i,(zone,span,frame) in enumerate(frames):
        bays=list(_enrich_bays(plan,i,span,s,size))
        motif_seed=rng.randint(1,1_000_000)
        _enrich_fascia(g,zone+" · резной антаблемент",frame,span,H,cove,s,style,
                       detail,relief,motif_seed,recipe,bays)
        _enrich_base(g,zone+" · резьба цоколя",frame,bays,H,s,style,detail,
                     relief,motif_seed,recipe,i==3)
        capzone=zone+" · акантовые капители"
        for j,(x,width) in enumerate(bays[1:],1):
            prev=bays[j-1][1]
            half_width=min(width*.094,prev*.094,149*s)
            _enrich_shaft(g,zone+" · резные пилястры",frame,x-width/2,H,half_width,s,
                          style,plan["ultra"]["pilaster"])
            _enrich_capital(g,capzone,frame,x-width/2,H*.809,half_width,s,
                            style,detail,relief,motif_seed+37*j,recipe,plan["ultra"]["capital"])
