"""Sculptural wall ornament assembled around the room's existing bays."""
import math
import random

if "_PalacePanel" not in globals():
    from palace_ornament import _PalacePanel, panel_outline
if "_enrich_bays" not in globals():
    from palace_enrichment import _enrich_bays, _enrich_offset, _enrich_profile


def _dense_wall_panel(g, zone, frame, style, detail, relief, seed, recipe):
    return _PalacePanel(g, zone, frame, 1000., 1000., style, min(detail, 2), relief, seed, recipe)


def _dense_wall_fan(panel, x, y, span, angle, lace, color):
    """Carved shell, palmette or acanthus crown with an undercut silhouette."""
    if lace == "shell":
        panel.scallop(x, y, angle-math.pi/2, span*.85, color)
    else:
        lobes = ((-.88,.64), (-.49,.82), (0,1), (.43,.90), (.84,.68))
        for offset, factor in lobes:
            panel.leaf(x, y, angle+offset, span*factor, span*.115, offset*span*.22, 21, color)
        if lace == "rosette":
            a = span*.26
            panel.rosette(x+a*math.cos(angle), y+a*math.sin(angle), a, 7, angle, color)


def _dense_wall_trim(panel, x, y, a, b, shape, rng, rhythm, scale):
    phase = rng.uniform(-.55,.55)
    wave = (3 if rhythm > .60 else 4, rng.uniform(.028,.057)+.022*rhythm)
    steps = 96
    points = []
    for i in range(steps):
        t = i/steps
        u, v = panel_outline(shape, t)
        swell = 1+.014*math.sin(math.tau*2*t+phase)+wave[1]*math.sin(math.tau*wave[0]*t+phase)**2
        points.append((u*swell,v*swell))
    mat = panel.main
    color = "plaster" if mat == "gold" else "gold"
    for squeeze, z, width, name in ((1,8,23,"shadow"), (.991,17,18,color),
                                    (.960,24,19,mat), (.937,31,8,"plaster"),
                                    (.911,17,12,mat), (.882,11,4,"shadow")):
        panel.tube(name, [(x+a*squeeze*u,y+b*squeeze*v,z*scale) for u,v in points],
                   width*scale,.76,True,8)
    # A canted shell chain follows selected arcs of the raised frame.
    step = 3 if rhythm > .65 else 4
    for i in range(step,steps,step):
        u,v = points[i]
        if abs(u) < .24 or i%12 == 0:
            continue
        px,py = x+a*.965*u,y+b*.965*v
        u2,v2=points[(i+1)%steps]
        angle=math.atan2(b*(v2-v),a*(u2-u))
        lobe = min(43*scale,a*.15)*(.86+.17*math.sin(12*i/steps+phase))
        panel.leaf(px,py,angle-.51,lobe,lobe*.28,lobe*.28,33*scale,mat,False)


def _dense_wall_bay(g, zone, frame, style, detail, relief, x, width, height, scale, seed, recipe,
                    spec, shape, branch):
    rng=random.Random(seed)
    panel=_dense_wall_panel(g, zone, frame, style, detail, relief, seed, recipe)
    a,b=width*.383,height*.286
    y=height*.533
    rhythm=spec["rhythm"]
    _dense_wall_trim(panel,x,y,a,b,shape,rng,rhythm,scale)
    amplitude=min(width*.27,height*.113)*spec["growth"]
    tilt=rng.uniform(-.25,.25)*(1+rhythm)
    lace=rng.choice(("shell","rosette","acanthus"))
    color=panel.trim if style!="bavarian" else panel.light
    # Mirrored visual weight accommodates unequal curves, leaves and shell heights.
    for end in (-1,1):
        root_y=y+end*b*(.71+.06*rng.random())
        direction=-end*math.pi/2+tilt
        for hand in (-1,1):
            side=x+hand*min(width*.065,amplitude*.27)
            length=amplitude*rng.uniform(.65,.94)
            lead=direction+hand*(.52+rng.random()*.41)
            panel.scroll(side,root_y,lead,length,-hand,True)
            if detail>=2:
                local_limit=(x-width*.39,y-b*.98,x+width*.39,y+b*.98)
                branch(g,zone,frame,side,root_y,lead,length*1.04,seed+end*31+hand,
                       style,min(2,detail),relief,depth=min(3,spec["order"]),spread=.64,
                       limit=local_limit)
        _dense_wall_fan(panel,x,root_y,amplitude*.57,direction,lace,color)
    # Design anchors at varied heights avoid copying one frame on every wall bay.
    heights=(.27,.54,.72) if rhythm>.38 else (.32,.65)
    for hand in (-1,1):
        for k,fraction in enumerate(heights):
            local_y=y+(2*fraction-1)*b+rng.uniform(-.075,.075)*b
            root_x=x+hand*a*rng.uniform(.77,.90)
            size=min(176*scale,amplitude*.47)*rng.uniform(.78,1.21)
            into=math.pi*.48 if (k+hand)%2 else -math.pi*.52
            panel.scroll(root_x,local_y,into+hand*.39,size,hand,True)
            panel.leaf(root_x,local_y,into+hand*.78,size*.93,size*.19,hand*size*.39,42*scale,color)
            if k==1:
                panel.rosette(root_x-hand*size*.19,local_y,size*.34,6,rng.random(),color)


def _dense_wall_window(g, zone, frame, style, detail, relief, x, width, height, scale, seed, recipe,
                       spec, branch):
    rng=random.Random(seed)
    panel=_dense_wall_panel(g,zone,frame,style,detail,relief,seed,recipe)
    w, crown, sill=width*.35,height*.795,height*.215
    rise=min(w*.78,(crown-sill)*.27)
    spring=crown-rise
    thickness=min(25*scale,width*.021)
    color=panel.main if style!="bavarian" else panel.light
    # Use the original arch centreline plus positive offsets to keep all glass open.
    for dx,dz,rad,mat in ((1.26,14,1.0,"shadow"),(1.15,26,.85,color),
                          (.68,44,.52,"plaster"),(.32,56,.22,panel.trim)):
        a=w+dx*thickness
        b=rise+dx*thickness
        curve=[(x+a,sill,dz*scale),(x+a,spring,dz*scale)]
        curve.extend((x+a*math.cos(math.pi*k/44),spring+b*math.sin(math.pi*k/44),dz*scale)
                     for k in range(1,45))
        curve.append((x-a,sill,dz*scale))
        panel.tube(mat,curve,thickness*rad,.78,False,10)
    usable=max(44,min(width*.084,158*scale))
    for hand in (-1,1):
        side=x+hand*width*.401
        for k in range(3):
            y=sill+(spring-sill)*(k+.64)/3.4
            lean=rng.uniform(.08,.23)*hand
            span=min((spring-sill)*.31,width*.119,usable*rng.uniform(1.35,2.18))
            panel.scroll(side,y,math.pi/2-lean,span,-hand,False)
            panel.leaf(side,y+span*.32,math.pi/2-lean,span*.47,usable*.24,hand*23*scale,
                       43*scale,panel.trim if k%2 else color)
        # The thick relief has floor-facing facets and small secondary stems.
        angle=math.pi*.43 if hand<0 else math.pi*.57
        ux=x+hand*w*.73
        uy=spring+rise*.83
        limit=(x-width*.49,uy-14*scale,x+width*.49,height*.897)
        branch(g,zone,frame,ux,uy,angle,usable*1.22,seed+hand*43,style,
               min(detail,2),relief,depth=min(3,spec["order"]),spread=.58,limit=limit)


def _dense_wall_portal(g, zone, frame, style, detail, relief, x, width, height, scale, seed, recipe,
                       spec, branch):
    rng=random.Random(seed)
    panel=_dense_wall_panel(g,zone,frame,style,detail,relief,seed,recipe)
    door=min(width*.61,1580*scale)
    h=height*.68
    radius=min((width-door)*.166,92*scale)
    color=panel.main
    for hand in (-1,1):
        centre=x+hand*(door*.5+radius*1.35)
        # Faceted pedestal, fluted barrel and stepped entablature.
        for y,head,deep,mat in ((.032,.46,.94,"shadow"),(.061,.28,1.44,color),
                                (.094,.34,.80,"plaster"),(.618,.50,1.46,color),
                                (.649,.28,1.73,"plaster"),(.673,.20,1.94,color)):
            f=_enrich_offset(frame,centre,0,36*scale)
            _enrich_profile(g,mat,zone,f,radius*1.30,height*y,head*radius,deep*radius)
        for offset in (-.67,-.33,0,.33,.67):
            sx=centre+offset*radius
            path=[(sx,height*.101,radius*1.27),
                  (sx,height*.369+offset*14*scale,radius*(1.59-.42*offset*offset)),
                  (sx,height*.613,radius*1.22)]
            panel.tube(color if abs(offset)>=.62 else "plaster",path,radius*.144,.85)
        for k in (-1,0,1):
            panel.leaf(centre+k*radius*.46,height*.602,math.pi/2-k*.36,
                       radius*2.0,radius*.32,k*radius*.42,82*scale,color)
        extent=min(width*.28,door*.31)
        lead=0.41 if hand>0 else math.pi-.41
        panel.scroll(x+hand*door*.06,h+height*.039,lead,extent*1.32,hand,True)
        branch(g,zone,frame,x+hand*door*.12,h+height*.035,lead,extent,seed+hand*97,
               style,min(2,detail),relief,depth=spec["order"],spread=.75,
               limit=(x-width*.48,h+16*scale,x+width*.48,height*.843))
    rise=min(height*.041,150*scale)
    for r,offset,z,mat in ((23,0,54,"shadow"),(17,.14,67,color),(9,-.11,82,"plaster"),
                           (4,.26,84,color)):
        path=[(x+u*door*.57,h+rise*(.48+.52*math.cos(math.pi*u))+offset*rise,z*scale)
              for u in (2*i/54-1 for i in range(55))]
        panel.tube(mat,path,r*scale,.92)
    _dense_wall_fan(panel,x,h+rise*1.20,rise*.78,math.pi/2,
                    rng.choice(("shell","rosette","acanthus")),color)


def _dense_wall_cove(g, zone, frame, size, span, scale, style, detail, relief, seed, recipe, bays, spec):
    L,W,H=size
    R=min(H*.115,min(L,W)*.075)
    rng=random.Random(seed)
    panel=_dense_wall_panel(g,zone,frame,style,detail,relief,seed,recipe)
    base=H-R
    color=panel.main
    for pitch,frequency,mat in ((.061,2,"shadow"),(.093,2,color),(.131,2,panel.light),(.20,3,color)):
        N=max(80,int(span/(37*scale)))
        points=[]
        for k in range(N+1):
            u=k/N
            theta=pitch+.042*math.sin(u*len(bays)*frequency*math.tau)
            x=(u-.5)*(span-85*scale)
            points.append((x,base+R*math.sin(theta),R*(1-math.cos(theta))+26*scale))
        panel.tube(mat,points,(11 if mat=="shadow" else 7)*scale,.77,False,7)
    for x,width in bays:
        for j,magnitude in enumerate((.29,.20,.39)):
            travel=(j-1)*width*.22+rng.uniform(-.034,.034)*width
            phi=.43+magnitude*.48+rng.uniform(-.026,.027)
            yy=base+R*math.sin(phi)
            zz=R*(1-math.cos(phi))+20*scale
            f=_enrich_offset(frame,x+travel,yy,zz)
            cap=_dense_wall_panel(g,zone,f,style,min(1,detail),relief,seed+j,recipe)
            length=min(magnitude*width,205*scale)
            if j==1:
                cap.scallop(0,-length*.19,0,length*.57,color)
            else:
                hand=-1 if j==0 else 1
                cap.scroll(0,0,math.pi if hand<0 else 0,length,hand,True)
                cap.leaf(0,0,math.pi/2, length*.57,length*.17,17*hand*scale,18*scale,panel.trim)


def dense_walls(g, plan, size, detail, relief, frames):
    """Fill the architectural transition zones while leaving door and window apertures clear."""
    if detail<2:
        return
    branch=globals().get("sprout")
    if branch is None:
        from palace_branching import sprout as branch
    L,W,H=size
    scale=min(H/4900,min(L,W)/6200,1.45)
    spec=plan["dense"]
    style=plan["style"]
    rng=random.Random(plan["seed"] ^ 0xCA10)
    recipe={key:plan[key] for key in ("curl","foliage","gilding")}
    recipe.update(plan.get("zone_tuning",{}).get("wall",{}))
    if recipe["foliage"] < .13:
        return
    for i,(name,span,frame) in enumerate(frames):
        bays=list(_enrich_bays(plan,i,span,scale,size))
        _dense_wall_cove(g,name+" · ажур падуги",frame,size,span,scale,style,detail,relief,
                         rng.randrange(1<<31),recipe,bays,spec)
        for j,(centre,width) in enumerate(bays):
            seed=rng.randrange(1<<31)
            args=(g,name+" · резной пролёт "+str(j+1),frame,style,detail,relief,
                  centre,width,H,scale,seed,recipe,spec)
            if i==0:
                _dense_wall_window(*args,branch)
            elif i==3 and j==len(bays)//2:
                _dense_wall_portal(*args,branch)
            elif plan.get("architecture",{}).get("walls") not in ("alcoves","gallery","canopy","grotto"):
                _dense_wall_bay(*args,plan["wall_shape"],branch)
