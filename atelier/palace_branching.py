"""Sculpted branching foliage. Paths and relief depths are expressed in millimetres."""
import math
import random

if "_PalacePanel" not in globals():
    from palace_ornament import _PalacePanel


def sprout(g, zone, frame, x, y, angle, length, seed, style, detail, relief,
           depth=3, spread=.6, limit=None, gild=True):
    """Grow linked stems and carved leaves inside a rectangular ornament footprint."""
    if length < 45:
        return
    rng = random.Random(seed)
    max_order = max(2, min(4, int(depth)))
    level = 1 if detail < 2 else 2
    carving = _PalacePanel(g, zone, frame, 1000, 1000, style, level, relief, seed,
                           {"gilding": .72 if gild else 0., "curl": .72, "foliage": .94})
    leaf_mat = "plaster" if style == "bavarian" or not gild else "gold"
    vein_mat = "gold" if gild else "plaster"

    def inside(px, py, margin):
        if limit is None:
            return True
        a, b, c, d = limit
        return a+margin <= px <= c-margin and b+margin <= py <= d-margin

    def branch(px, py, heading, reach, radius, rise, order, hand):
        # A S-curve gradually twists into a volute at the tip. Offshoots start at its skin.
        side_bend = hand * rng.uniform(.16, .34) * spread
        curl = hand * rng.uniform(.67, 1.39) * spread
        phase = rng.uniform(-.25, .25)
        cos, sin = math.cos(heading), math.sin(heading)

        def pos(t):
            u = reach * (t - .14*t**4)
            v = reach * (side_bend*math.sin(math.pi*(1.2*t + phase*t)) + curl*.24*t**3)
            z = rise + min(49.,reach*.16)*math.sin(math.pi*t*.85)
            return px+cos*u-sin*v, py+sin*u+cos*v, z

        points = []
        steps = (24 if order==0 else 13) if detail>=2 else (16 if order==0 else 9)
        for i in range(steps+1):
            t = i/steps
            point = pos(t)
            if not inside(*point[:2],radius*1.16):
                break
            points.append(point)
        if len(points)<4:
            return
        end = (len(points)-1)/steps
        radii = [max(.8,radius*(1-.91*(i/steps))**.81) for i in range(len(points))]
        carving.tube(leaf_mat, points, radii, .72, sides=8 if order<2 else 5)
        if detail>=2 and order<2:
            crest = [(a,b,c+r*.64) for (a,b,c),r in zip(points,radii)]
            carving.tube(vein_mat, crest, [max(.44,r*.16) for r in radii], .85, sides=5)

        def direction(t):
            a,b,_ = pos(t)
            c,d,_ = pos(min(1,t+.015))
            return math.atan2(d-b,c-a)

        count = 3 if order<2 else 2
        for index in range(count):
            t = .22+index*.24
            if t>end-.025:
                continue
            a,b,c = pos(t)
            turn = hand*(-1)**index
            tilt = direction(t)+turn*rng.uniform(.54,1.12)
            blade = min(225.,reach*rng.uniform(.17,.25))*(1-.23*t)
            margin = blade*1.03
            if inside(a,b,margin):
                carving.leaf(a,b,tilt,max(11.,blade),max(3.,blade*.25),
                             turn*blade*.18,c,leaf_mat,order<2)

        if order+1<max_order and reach>65:
            forks=(.27,.56,.76) if order==0 else (.43,.71)
            for i,t in enumerate(forks):
                if t>end-.04:
                    continue
                a,b,c = pos(t)
                turn=hand*(-1)**i
                course = direction(t)+turn*rng.uniform(.46,.98)*(spread+.45)
                child = reach*rng.uniform(.38,.53)*(1-.32*t)
                branch(a,b,course,child,radius*.54,c,order+1,-turn)
        elif detail>=2 and reach>55:
            a,b,c = points[-1]
            if inside(a,b,reach*.11):
                carving.pearl(a,b,c,reach*.052,vein_mat)

    radius=max(3.6,min(33.,length*.044))
    branch(x,y,angle,length,radius,max(4.,radius*.38),0,rng.choice((-1,1)))
