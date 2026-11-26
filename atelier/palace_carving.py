"""Bounded recursive relief in millimetres, shared by Rhino and OBJ export."""
import math
import random


# Deliberately uneven bevels with narrow grooves either side of a carved ridge.
_CARVED_SECTION = (
    (-1., .045), (-.86, .14), (-.68, .49), (-.51, .32), (-.30, .54),
    (-.10, .83), (0., 1.), (.12, .82), (.29, .40), (.48, .23),
    (.60, .45), (.76, .30), (1., .045),
)
_NARROW_SECTION = tuple(_CARVED_SECTION[i] for i in (0,2,3,6,9,10,12))


def carving_fraction(value):
    if value is None:
        return None
    percent = float(value)
    if not 0 <= percent <= 100:
        raise ValueError("Влияние формулы должно быть от 0 до 100 %")
    return percent / 100


def _carved_ribbon(geom, zone, frame, path, section=_CARVED_SECTION, *,
                   material="plaster", loop=False, fits=None, foot=-2.):
    """Sweep an articulated height profile and close it against its mounting surface."""
    if len(path)<3:
        return
    if section is _CARVED_SECTION and max(p[2] for p in path)<21.:
        section=_NARROW_SECTION
    n, width = len(path), len(section)
    front = []
    for i, (x, y, spread, lift) in enumerate(path):
        before = path[(i-1) % n if i or loop else 0]
        after = path[(i+1) % n if i+1 < n or loop else i]
        dx, dy = after[0]-before[0], after[1]-before[1]
        distance = math.hypot(dx, dy)
        if distance < .001:
            return
        nx, ny = -dy/distance, dx/distance
        for cross, high in section:
            u, v = x+cross*spread*nx, y+cross*spread*ny
            if fits is not None and not fits(u, v):
                return
            front.append((u, v, high*lift))
    vertices = [frame(x, y, z) for x, y, z in front]
    # The back needs only its boundaries. Keep full rows at the end caps so
    # the profile closes with no T-junctions.
    back=[]
    for i in range(n):
        row=[]
        cols=range(width) if not loop and i in (0,n-1) else (0,width-1)
        for j in cols:
            x,y,_=front[i*width+j]
            row.append(len(vertices))
            vertices.append(frame(x,y,foot))
        back.append(row)
    faces = []
    for i in range(n if loop else n-1):
        j1=(i+1)%n
        a,b=i*width,j1*width
        rear_a,rear_b=back[i],back[j1]
        for j in range(width-1):
            faces.append((a+j,b+j,b+j+1,a+j+1))
        faces.extend(((a,rear_a[0],rear_b[0],b),
                      (a+width-1,b+width-1,rear_b[-1],rear_a[-1])))
        if len(rear_a)>2:
            faces.extend((u,v,rear_b[0]) for u,v in zip(rear_a,rear_a[1:]))
            faces.append((rear_a[-1],rear_b[-1],rear_b[0]))
        elif len(rear_b)>2:
            faces.append((rear_a[0],rear_a[-1],rear_b[-1]))
            faces.extend((rear_a[0],v,u) for u,v in zip(rear_b,rear_b[1:]))
        else:
            faces.append((rear_a[0],rear_a[-1],rear_b[-1],rear_b[0]))
    if not loop:
        last=(n-1)*width
        for j in range(width-1):
            faces.extend(((j,j+1,back[0][j+1],back[0][j]),
                          (last+j,back[-1][j],back[-1][j+1],last+j+1)))
    geom.mesh(material,zone,vertices,faces)
    geom.carved_pieces+=1
    return True


def _carved_leaf(geom, zone, frame, start, direction, length, width, lift,
                 hand, amount, detail, fits):
    """A tapered acanthus blade with a crease and progressively smaller lobes."""
    x, y = start
    cs, sn = math.cos(direction), math.sin(direction)
    path = []
    limit=21+5*detail if width>30 else 11+4*detail
    steps = max(10,min(limit,math.ceil(length/(8.5-detail))+6))
    for i in range(steps+1):
        t = i/steps
        bell = max(.045, math.sin(math.pi*t)**.83)
        # Smaller orders articulate the margin without jittering its mesh vertices.
        lobe = (1+.22*math.cos(8*math.pi*t+.70)
                  +.14*amount*math.cos(16*math.pi*t-1.1)
                  +.05*amount*math.sin(32*math.pi*t))
        side = hand*length*(.22+.15*amount)*t*t
        path.append((x+cs*length*t-sn*side, y+sn*length*t+cs*side,
                     width*bell*lobe, lift*(.18+.82*bell)*(1-.32*t)))
    _carved_ribbon(geom,zone,frame,path,fits=fits)


def _carved_scroll(geom, zone, frame, start, direction, length, width, lift,
                   hand, amount, seed, detail, fits, generations=2):
    """Build a stem, a curled tip and attached secondary blades at diminishing scales."""
    rng = random.Random(seed)
    x, y = start
    cs, sn = math.cos(direction), math.sin(direction)
    bend = hand*(.13+amount*rng.uniform(-.075,.10))
    turn = .89+amount*rng.uniform(-.19,.23)
    edge = .67
    radius = .147*length
    across, travel = bend*length, edge*length

    def point(t):
        if t <= edge:
            u = t/edge
            forward, side = t*length, across*(u*u*(3-2*u))
        else:
            u = (t-edge)/(1-edge)
            angle = math.tau*turn*u
            r = radius*(1-.77*u)
            forward = travel+r*math.sin(angle)
            side = across+hand*(radius-r*math.cos(angle))
        return x+cs*forward-sn*side, y+sn*forward+cs*side

    steps = max(16,min(32+8*detail,math.ceil(length/(17.-3*detail))+8))
    path = [(*point(i/steps),width*(1-.91*i/steps)**1.27,
             lift*(1-.78*i/steps)**.85) for i in range(steps+1)]
    if not _carved_ribbon(geom,zone,frame,path,fits=fits):
        return
    for j,t in enumerate((.20,.39,.56,.68)):
        root = point(t)
        near = point(t+.008)
        forward = math.atan2(near[1]-root[1],near[0]-root[0])
        side = hand*(-1)**j
        leaf_len = length*(.29-.22*t)*(1+amount*rng.uniform(-.20,.20))
        _carved_leaf(geom,zone,frame,root,forward+side*(.81+.3*amount),
                     leaf_len,leaf_len*.27,lift*(.66-.42*t),-side,amount,detail,fits)
        if generations>1 and j in (0,2) and leaf_len>36:
            daughter = length*(.33-.17*t)*(1+amount*rng.uniform(-.23,.25))
            _carved_scroll(geom,zone,frame,root,forward-side*(.72+.44*amount),
                           daughter,width*.56,lift*.64,-side,amount,
                           rng.randrange(2**31),detail,fits,generations-1)


def _carved_fan(geom, zone, frame, center, spread, lift, direction,
                amount, seed, detail, fits):
    """Fluted shell formed by connected ribs that fan out from one root."""
    rng = random.Random(seed)
    for k in range(-4,5):
        ratio = k/4
        angle = direction+ratio*(.97+.17*amount)
        length = spread*(1-.33*ratio*ratio)*(1+amount*rng.uniform(-.075,.075))
        _carved_leaf(geom,zone,frame,center,angle,length,
                     length*.105,lift*(1-.42*abs(ratio)),1 if k>=0 else -1,amount,detail,fits)


def _carved_sites(ring,count):
    """Space ornament along a moulding by length, including on elongated fields."""
    lengths=[0.]
    for i,(x,y) in enumerate(ring):
        u,v=ring[(i+1)%len(ring)]
        lengths.append(lengths[-1]+math.hypot(u-x,v-y))
    edge=0
    for i in range(count):
        travel=lengths[-1]*i/count
        while travel>lengths[edge+1]:
            edge+=1
        x,y=ring[edge]
        u,v=ring[(edge+1)%len(ring)]
        t=(travel-lengths[edge])/(lengths[edge+1]-lengths[edge])
        yield x+t*(u-x),y+t*(v-y),math.atan2(v-y,u-x)


def _carved_web(g, zone, frame, a, b, cell, rise, amount, seed, detail, fits, family):
    """Lay two crossing families of curved ribs, then branch from their joints."""
    if min(a,b)<cell*.52:
        return
    rng=random.Random(seed)
    phase=rng.uniform(-.25,.25)
    taper=.65 if family==0 else .38 if family==1 else .52
    pitch=(.78 if family==0 else .55 if family==1 else .91)
    radius=max(3.,min(16.,cell*.043))

    def point(u,k,hand):
        # Low-frequency corrugation shifts each line. The next two frequencies
        # have progressively smaller amplitudes and follow the same curve.
        v=(u/cell)*math.pi
        wave=(.14*math.sin(v+hand*k*.32+phase)
              +amount*(.060*math.sin(2*v+.43*k)+.024*math.sin(4*v-.29*k)))
        return u,hand*pitch*u+cell*(k+taper*wave)

    limit=math.ceil((b+pitch*a)/cell)+1
    samples=max(20,math.ceil(a*2/(cell/9)))
    for hand in (-1,1):
        for k in range(-limit,limit+1):
            span=[]
            width=radius*(1.27 if k%3==0 else .74)
            profile=rise*(1. if k%3==0 else .71)
            for j in range(samples+1):
                x,y=point(a*(j/samples*2-1),k,hand)
                if all(fits(x+dx*width,y+dy*width) for dx,dy in ((-1,0),(1,0),(0,-1),(0,1))):
                    span.append((x,y,width,profile))
                else:
                    if len(span)>=4:
                        _carved_ribbon(g,zone,frame,span,fits=fits)
                    span=[]
            if len(span)>=4:
                _carved_ribbon(g,zone,frame,span,fits=fits)

    spacing=cell*(1.25 if detail==1 else .94)
    for j in range(-math.floor(a/spacing),math.floor(a/spacing)+1):
        for k in range(-limit,limit+1):
            x,y=point(j*spacing*.98,k,1)
            if not fits(x,y):
                continue
            turn=(-1)**(j+k)
            length=cell*(.37 if (j+k)%3 else .51)
            theta=math.atan(pitch)+turn*1.12
            if (j+k)%2==0:
                _carved_scroll(g,zone,frame,(x,y),theta,length,cell*.067,rise*1.85,
                               turn,amount,seed+1553*j+31*k,detail,fits,2)
            _carved_leaf(g,zone,frame,(x,y),theta+turn*.62,length*.81,
                         cell*.084,rise*1.49,turn,amount,detail,fits)


def carve_field(panel, amount, seed, crown=None):
    """Use one moulding and carving vocabulary on wall panels and ceiling fields."""
    panel.mount(trim=False)
    g, zone, frame = panel.geom, panel.zone, panel.frame
    a, b = panel.a*panel.unit, panel.b*panel.unit
    scale = min(a,b)
    depth = min(panel.depth,1.65)
    rim = [(x*panel.unit,y*panel.unit) for x,y in panel.ring(.975)]
    radial = zone.startswith("Плафон")
    narrow = max(10.,min(72. if radial else 53.,scale*(.086 if radial else .060)))
    lift = min(narrow*1.51,92.)*depth
    reveal = [(x*panel.unit,y*panel.unit) for x,y in panel.ring(1.006)]
    _carved_ribbon(g,zone,frame,[(x,y,narrow*1.12,lift*.47) for x,y in reveal],
                   material="shadow",loop=True,foot=-1.)
    _carved_ribbon(g,zone,frame,[(x,y,narrow,lift) for x,y in rim],loop=True,foot=-1.)
    inner = [(x*panel.unit,y*panel.unit) for x,y in panel.ring(.906)]
    _carved_ribbon(g,zone,frame,[(x,y,max(3.5,narrow*.31),lift*.41) for x,y in inner],
                   loop=True,foot=-.3)
    if panel.open_center or scale<100:
        return

    outline = [(x*panel.unit,y*panel.unit) for x,y in panel.ring(.965)]

    def fits(x,y):
        if abs(x)<.49*a and abs(y)<.49*b:
            return True
        inside = False
        for i,(u,v) in enumerate(outline):
            w,z = outline[i-1]
            if (v>y)!=(z>y) and x<(w-u)*(y-v)/(z-v)+u:
                inside = not inside
        return inside

    def fringe_fits(x,y):
        return fits(x,y) and math.hypot(x/a,y/b)>.53

    rim_roots=[(x*panel.unit,y*panel.unit) for x,y in panel.ring(.884)]
    count=(10 if panel.d==1 else 16 if radial else 12)+round(8*panel.leafiness)
    for k,(x,y,tangent) in enumerate(_carved_sites(rim_roots,count)):
        direction=math.atan2(-y/b,-x/a)
        root=(x,y)
        reach=scale*(.35 if k%2==0 else .25)
        if k%2==0:
            _carved_fan(g,zone,frame,root,reach*.67,lift*.91,direction,amount,seed+k%3,
                        panel.d,fringe_fits)
        for hand in (-1,1):
            _carved_scroll(g,zone,frame,root,direction+hand*.82,reach,narrow*.83,lift*1.16,
                           hand,amount,seed+61*(k%3),panel.d,fringe_fits,2)
        _carved_leaf(g,zone,frame,root,tangent+.39,reach*.78,narrow*.69,lift*.81,
                     1,amount,panel.d,fringe_fits)
    if panel.painted:
        return

    if crown is not None:
        kind,headroom=crown
        # The shell shares a root with the top rail. Its foliage fills the
        # spandrel without a freestanding moulding above it.
        x,y=panel.ring(.968)[len(rim)//4]
        root=(x*panel.unit,y*panel.unit)
        reach=min(headroom*.84,scale*(.88 if kind=="canopy" else 1.01))
        if reach>100:
            def crest_fits(x,y):
                return abs(x)<a*.83 and b*.78<=y<=b+headroom*.91
            _carved_fan(g,zone,frame,root,reach*.77,lift*1.42,math.pi/2,amount,seed,panel.d,crest_fits)
            for hand in (-1,1):
                direction=math.pi/2+hand*(.94 if kind=="canopy" else 1.13)
                _carved_scroll(g,zone,frame,root,direction,reach,narrow*1.11,lift*1.55,
                               hand,amount,seed,panel.d,crest_fits,3)

    # Recessed, interlaced carving behind the large projecting motifs. The
    # projection and bandwidth diminish from the stems down to these ribs.
    cell=max(128.,min(385.,scale*(.41-.14*panel.leafiness)))
    def bed_fits(x,y):
        return fits(x,y) and math.hypot(x/a,y/b)>.16
    family=(seed+int(panel.shape=="lobed"))%3
    _carved_web(g,zone,frame,a*.90,b*.90,cell, min(26.,cell*.104)*depth,
                amount,seed,panel.d,bed_fits,family)

    # A tall panel has a vertical bouquet. A ceiling field reads as a radial centre.
    width = max(7.,min(47.,scale*.067))
    rise = min(83.,width*1.8)*depth
    stem = scale*(.69+.25*panel.leafiness)
    if radial:
        rays = 12 if panel.motif in ("flower","sunburst") else 8
        inner_radius = scale*.19
        for ratio,level in ((.72,.54),(1.,1.),(1.34,.67)):
            radius = inner_radius*ratio
            ring = []
            for i in range(144):
                theta = math.tau*i/144
                corrugation = 1+(.054+.036*amount)*math.cos(rays*theta)
                ring.append((radius*corrugation*math.cos(theta),radius*corrugation*math.sin(theta),
                             width*.52*level,rise*level))
            _carved_ribbon(g,zone,frame,ring,loop=True)
        for k in range(rays):
            angle = math.tau*k/rays
            root = (inner_radius*math.cos(angle),inner_radius*math.sin(angle))
            _carved_scroll(g,zone,frame,root,angle+.16*(-1)**k,stem*.90,width,rise,(-1)**k,
                           amount,seed+97*min(k,rays-k),panel.d,fits,3)
            halfway=angle+math.pi/rays
            start=(inner_radius*.94*math.cos(halfway),inner_radius*.94*math.sin(halfway))
            _carved_scroll(g,zone,frame,start,halfway,stem*.54,width*.76,rise*.92,
                           (-1)**(k+1),amount,seed+3109+k%3,panel.d,fits)
            _carved_leaf(g,zone,frame,root,angle+.31,stem*.47,width*1.36,rise*.83,
                         (-1)**k,amount,panel.d,fits)
        panel.rosette(0,0,scale/panel.unit*.116,rays,0.,"plaster")
    else:
        layers = ((-.57,.94),(-.17,1.23),(.24,.97)) if b>a*1.12 else ((-.30,1.2),(.24,.88))
        for k,(offset,factor) in enumerate(layers):
            root=(0.,b*offset)
            _carved_fan(g,zone,frame,root,stem*.54*factor,rise*.87,math.pi/2,
                        amount,seed+53*k,panel.d,fits)
            for hand in (-1,1):
                _carved_scroll(g,zone,frame,root,math.pi/2-hand*.94,stem*factor,
                               width*factor,rise*factor,hand,amount,seed+103*k,panel.d,fits,3)


def carve_wall_bay(g, zone, frame, center, span, lower, upper, depth, foliage, amount, seed, detail):
    height = upper-lower
    width = min(span*.435,height*1.68)
    lift = min(91.,height*.22)*min(depth,1.7)
    line = lambda y: [(center+width*t,lower+y*height,height*.023,lift*.48)
                      for t in (-1.,0.,1.)]
    _carved_ribbon(g,zone,frame,line(.16))
    _carved_ribbon(g,zone,frame,line(.87))
    x,y=center,lower+height*.22
    def fits(u,v):
        return abs(u-center)<=width and lower<=v<=upper
    _carved_fan(g,zone,frame,(x,y),height*.56,lift,math.pi/2,amount,seed,detail,fits)
    reach = min(width*.95,height*1.20)*(.77+.22*foliage)
    for level in (.22,.67):
        for hand in (-1,1):
            angle=.27 if hand>0 else math.pi-.27
            turn=hand if level < .5 else -hand
            _carved_scroll(g,zone,frame,(x,lower+height*level),angle,reach,
                           height*.102,lift*1.22,turn,amount,seed,detail,fits)
    sprays=4+round(3*foliage)
    for k in range(-sprays,sprays+1):
        u=center+width*k*.82/sprays
        _carved_fan(g,zone,frame,(u,lower+height*.77),height*(.24 if k%2 else .33),
                    lift*.69,-math.pi/2,amount,seed+min(abs(k),3),detail,fits)


def carve_capital(g, zone, frame, x, z, base, radius, levels, amount, detail):
    """Attach two ranks of acanthus to the shaped crown of a column."""
    def radius_at(v):
        for (lo,a),(hi,b) in zip(levels,levels[1:]):
            if v<=hi:
                return radius*(a+(b-a)*max(0.,(v-lo)/(hi-lo)))
        return radius*levels[-1][1]

    for layer,height in enumerate((.13*radius,.77*radius)):
        count=12
        for i in range(count):
            angle=math.tau*(i+layer*.5)/count
            def surface(u,v,w):
                row=radius_at(v)
                theta=angle-u/row
                projection=row+w-.015*radius
                return frame(x+projection*math.cos(theta),base+v,z-projection*math.sin(theta))
            reach=radius*(.91-.13*layer)
            hand=(-1)**i
            _carved_leaf(g,zone,surface,(0.,height),math.pi/2+hand*.13,reach,
                         radius*.22,radius*(.19-.043*layer),hand,amount,detail,None)


def carve_arch(g, zone, frame, center, spring, run, rise, projection, detail, amount, seed):
    """Continue the foliage up the arch in fitted voussoir ornaments."""
    scale=min(run,rise)
    count=max(9,min(25,round(run/61)))*2+1
    step=math.pi/(count+1)
    for i in range(1,count+1):
        theta=i*step
        x=center+run*math.cos(theta)
        y=spring+rise*math.sin(theta)
        mount=lambda u,v,h:frame(u,v,projection+h)
        angle=math.atan2(run*math.sin(theta),rise*math.cos(theta))
        pair=min(i,count+1-i)
        length=min(scale*.19,77.)*(.92+.14*(pair%3))
        hand=-1 if i<=count/2 else 1
        _carved_leaf(g,zone,mount,(x,y),angle+hand*.77,length,
                     length*.35,length*.52,hand,amount,detail,None)
        if pair%4==1:
            _carved_scroll(g,zone,mount,(x,y),angle-hand*.85,length*1.43,
                           length*.34,length*.62,-hand,amount,seed+pair,detail,None,1)


def carve_vault(g, zone, frame, size, plan, detail, relief, amount, clear):
    """Grow from the perimeter toward the principal field on the actual vault."""
    a,b = size[0]*.5,size[1]*.5
    scale = min(a,b)
    depth = min(relief,1.55)
    rim = []
    for i in range(240):
        t = math.tau*i/240
        u,v = math.cos(t),math.sin(t)
        rim.append((a*.935*math.copysign(abs(u)**.34,u),
                    b*.935*math.copysign(abs(v)**.34,v),
                    min(78.,scale*.022),min(121.,scale*.044)*depth))
    _carved_ribbon(g,zone,frame,rim,loop=True)
    inner = [(.978*x,.978*y,w*.37,h*.67) for x,y,w,h in rim]
    _carved_ribbon(g,zone,frame,inner,loop=True)
    stages = plan.get("refinement",{}).get("stages",{})
    dense=plan.get("dense",{})
    growth=math.sqrt(dense.get("growth",1.))
    generations=max(2,min(4,dense.get("order",3)))
    if "rims" in stages or "frieze" in stages:
        generations=max(3,generations)

    def fits(x,y):
        return abs(x)<.946*a and abs(y)<.946*b and clear(x,y)

    foliage=max(0.,min(1.,plan["foliage"]+g.foliage_delta))
    cell=max(192.,min(405.,scale*(.104-.044*foliage)))
    _carved_web(g,zone,frame,a*.886,b*.886,cell,min(35.,cell*.106)*depth,
                amount,plan["seed"],detail,fits,plan["seed"]%3)

    # Broad axes continue the wall rhythm, with the same vocabulary at both scales.
    for axis in range(2):
        along, across = (a,b) if axis==0 else (b,a)
        count=max(3,plan["wall_bays"] if axis==0 else round(plan["wall_bays"]*b/a))
        for i in range(count):
            longitudinal=along*(.83*(2*(i+.5)/count-1))
            salt=plan["seed"]+axis*104729+min(i,count-1-i)*1451
            rng=random.Random(salt)
            for side in (-1,1):
                origin=(longitudinal,side*across*.927) if axis==0 else (side*across*.927,longitudinal)
                direction=-side*math.pi/2 if axis==0 else (math.pi if side>0 else 0.)
                room = min(scale*.49,along*1.11/count)*(.94+amount*rng.uniform(-.12,.20))*growth
                profile=min(79.,room*.088)
                for hand in (-1,1):
                    angle=direction+hand*(.65+.12*amount)
                    for factor in (1.,.79,.61):
                        # Choose the longest carving that fits between the framework and the panel.
                        before=len(g.parts.get((zone,"plaster"),((),()))[0])
                        _carved_scroll(g,zone,frame,origin,angle,room*factor,
                                       profile*factor,profile*1.70*depth*factor,
                                       hand*side,amount,salt,detail,fits,generations)
                        if len(g.parts[(zone,"plaster")][0])>before:
                            break
    perimeter=[(x*.982,y*.982) for x,y,_,_ in rim]
    count=max(24,min(64,round((a+b)/175)))
    for k,(x,y,tangent) in enumerate(_carved_sites(perimeter,count)):
        inward=math.atan2(-y/b,-x/a)
        length=min(360.,scale*.103)*(1. if k%2==0 else .74)
        start=(x,y)
        _carved_scroll(g,zone,frame,start,inward+(-1)**k*.91,length,length*.12,
                       length*.19*depth,(-1)**k,amount,plan["seed"]+k%7,
                       detail,fits,2)
        _carved_leaf(g,zone,frame,start,tangent+.52,length*.66,length*.10,
                     length*.15*depth,1,amount,detail,fits)

    # Fit paired, inward-curled ornaments into the larger gaps between fields.
    # Rank by physical clearance and keep matching clearances on both sides.
    spacing=min(490.,scale*.137)
    candidates=[]
    for i in range(1,9):
        x=a*i*.89/9
        for j in range(1,8):
            y=b*j*.87/8
            for radius in (spacing,spacing*.76,spacing*.55):
                if all(fits(side*x+radius*math.cos(k*math.tau/10),
                            end*y+radius*math.sin(k*math.tau/10))
                       for side in (-1,1) for end in (-1,1) for k in range(10)):
                    candidates.append((radius,x,y))
                    break
    chosen=[]
    for radius,x,y in sorted(candidates,reverse=True):
        if any(math.hypot(x-u,y-v)<1.84*(radius+r) for r,u,v in chosen):
            continue
        chosen.append((radius,x,y))
        if len(chosen)==5:
            break
    for i,(radius,x,y) in enumerate(chosen):
        for side in (-1,1):
            for end in (-1,1):
                start=(side*x,end*y)
                inward=math.atan2(-end*y/b,-side*x/a)
                length=radius*1.22
                for hand in (-1,1):
                    _carved_scroll(g,zone,frame,start,inward+hand*1.22,length,
                                   radius*.13,radius*.18*depth,side*end*hand,
                                   amount,plan["seed"]+i*2617,detail,fits,3)
                _carved_fan(g,zone,frame,start,radius*.66,radius*.17*depth,
                            inward,amount,plan["seed"]+i*2617,detail,fits)
