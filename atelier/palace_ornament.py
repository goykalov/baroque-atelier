"""Closed, indexed relief surfaces in panel coordinates. All dimensions are in millimetres."""
import math
import random


def panel_outline(shape, t):
    """Return the outer silhouette in normalised coordinates; t makes one CCW revolution."""
    a = 2 * math.pi * t
    x, y = math.cos(a), math.sin(a)
    if shape == "octagon":
        r = min(1 / max(abs(x), abs(y)), 1.62 / (abs(x) + abs(y)))
        return x * r, y * r
    if shape == "oval":
        return x, y
    if shape == "lobed":
        r = (1 + .095 * math.cos(4*a) - .043 * math.cos(8*a)) / 1.055
        return x * r, y * r
    if shape == "arch" and y >= 0:
        return x, .24 + .76 * y
    q = .36 if shape == "rect" else .46
    u = math.copysign(abs(x)**q, x)
    v = math.copysign(abs(y)**q, y)
    return u, (.24 + 1.24 * v if shape == "arch" else v)


def _palace_bezier(points, t):
    s = 1 - t
    weights = (s**3, 3*s*s*t, 3*s*t*t, t**3)
    return tuple(sum(w*p[j] for p, w in zip(points, weights)) for j in (0, 1))


class _PalacePanel:
    def __init__(self, geom, zone, frame, width, height, style, detail, relief, seed, recipe):
        self.geom, self.zone, self.frame = geom, zone, frame
        self.unit = min(width, height)/1000.
        self.a, self.b = .448*width/self.unit, .448*height/self.unit
        self.style, self.d, self.depth = style, int(max(1, min(3, detail))), max(.05, relief)
        self.rand = random.Random(seed)
        self.curl = float(recipe.get("curl", .5))
        self.leafiness = float(recipe.get("foliage", .65))
        self.gilt = float(recipe.get("gilding", .55))
        self.motif = recipe.get("motif", "shell")
        self.elements = set(recipe.get("elements", ["scroll", "spray", "beads"]))
        self.shape = recipe.get("shape", {"bavarian":"lobed", "russian":"arch", "mexican":"octagon"}[style])
        self.open_center = recipe.get("center") == "empty"
        self.painted = bool(recipe.get("painted"))
        self.ultra=recipe.get("ultra")
        self.main = "gold" if self.gilt >= .50 else "plaster"
        self.light = "plaster" if self.gilt < .83 else "gold"
        self.trim = "gold" if self.gilt > .10 else "accent"
        self.stem = self.main if style != "bavarian" else self.light
        self.turns = .91 + .33*self.curl + self.rand.uniform(-.07, .07)
        self.stretch = self.rand.uniform(.89, 1.12)
        self.phase = self.rand.uniform(-.21, .21)

    def emit(self, mat, vv, ff):
        u, z = self.unit, self.unit*self.depth
        self.geom.mesh(mat, self.zone, [self.frame(x*u, y*u, h*z) for x,y,h in vv], ff)

    def sheet(self, mat, rows, underside):
        """Close a relief with the same perimeter vertices on top and underside."""
        h, w = len(rows), len(rows[0])
        n = h*w
        verts = [v for row in rows for v in row]
        verts += [(x,y,z-underside) for x,y,z in verts]
        a,b,c = rows[h//2][w//2],rows[h//2+1][w//2],rows[h//2][w//2+1]
        ccw = (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0]) >= 0
        ff = []
        for i in range(h-1):
            for j in range(w-1):
                k = i*w+j
                q = (k,k+w,k+w+1,k+1)
                if not ccw:
                    q = q[::-1]
                ff.extend((q, tuple(k+n for k in reversed(q))))
        rim = list(range(0,n,w)) + list(range(n-w+1,n)) + list(range(n-w-1,0,-w)) + list(range(w-2,0,-1))
        if not ccw:
            rim.reverse()
        for i,k in enumerate(rim):
            l = rim[(i+1)%len(rim)]
            ff.append((k,k+n,l+n,l))
        self.emit(mat, verts, ff)

    def tube(self, mat, path, radii, flat=.72, closed=False, sides=None):
        n = len(path)
        sides = sides or (5+self.d)
        vv, ff = [], []
        for i,(x,y,z) in enumerate(path):
            p = path[(i-1)%n] if closed or i else path[0]
            q = path[(i+1)%n] if closed or i+1<n else path[-1]
            dx,dy = q[0]-p[0], q[1]-p[1]
            length = math.hypot(dx,dy)
            nx,ny = -dy/max(1e-9,length), dx/max(1e-9,length)
            r = radii[i] if isinstance(radii, list) else radii
            for j in range(sides):
                angle = 2*math.pi*j/sides
                d = r*math.cos(angle)
                vv.append((x+d*nx,y+d*ny,z+r*flat*math.sin(angle)))
        for i in range(n if closed else n-1):
            for j in range(sides):
                a, b = i*sides+j, i*sides+(j+1)%sides
                c, d = (b+sides)%(n*sides), (a+sides)%(n*sides)
                ff.append((a,b,c,d))
        if not closed:
            for i in (0,n-1):
                mid = len(vv)
                vv.append(path[i])
                for j in range(sides):
                    a,b = i*sides+j,i*sides+(j+1)%sides
                    ff.append((mid,b,a) if i==0 else (mid,a,b))
        self.emit(mat,vv,ff)

    def pearl(self, x,y,z,rad,mat):
        # A low cabochon with a rounded crown and a flat closed setting.
        n = 6+2*self.d
        vv = [(x,y,z+rad*.83),(x,y,z-rad*.43)]
        for r,h in ((.62,.59),(1,0),(.79,-.43)):
            for j in range(n):
                a = j*2*math.pi/n
                vv.append((x+rad*r*math.cos(a),y+rad*r*math.sin(a),z+rad*h))
        ff = []
        for j in range(n):
            a,b = 2+j,2+(j+1)%n
            ff.extend(((0,a,b),(b,a,a+n,b+n),(b+n,a+n,a+2*n,b+2*n),(1,b+2*n,a+2*n)))
        self.emit(mat,vv,ff)

    def leaf(self,x,y,angle,length,width,bend,z,mat,serrated=True):
        # The lobes are fuller near the root and curl into a raised, twisted tip.
        cs,sn = math.cos(angle),math.sin(angle)
        nr = 8 + 3*self.d if serrated else 6+self.d
        across = 4 if self.d<3 else 6
        rows, vein = [], []
        for i in range(nr+1):
            t = i/nr
            axis = length*t
            sideways = bend*t*t
            px,py = x+cs*axis-sn*sideways,y+sn*axis+cs*sideways
            dx,dy = cs*length-sn*2*bend*t,sn*length+cs*2*bend*t
            mag = math.hypot(dx,dy)
            nx,ny = -dy/mag,dx/mag
            bell = max(.018,math.sin(math.pi*t))**.72
            tooth = .80+.20*math.cos(8.2*math.pi*t+.4) if serrated else 1
            wing = width*bell*tooth
            lift = width*(.44*math.sin(math.pi*t)+.27*t**4)
            row = []
            for j in range(across+1):
                s = 2*j/across-1
                w = s*wing*(1+.12*s*math.sin(2*math.pi*t))
                # A transverse fold on either side catches oblique light.
                ridge = width*bell*(.52*(1-abs(s))**2+.14*math.cos(2*math.pi*s))
                h = z+lift+ridge+.18*s*width*math.sin(2.7*math.pi*t)
                row.append((px+nx*w,py+ny*w,h))
            vein.append(row[across//2])
            rows.append(row)
        self.sheet(mat,rows,max(1.05,.18*width))
        if serrated and self.d>=2 and width>=5:
            pts = [(px,py,pz+.21) for px,py,pz in vein[1:-1:2]]
            self.tube(self.trim,pts,[max(.34,width*.089*(1-.76*i/(len(pts)-1))) for i in range(len(pts))],.64,sides=4)

    def scallop(self,x,y,ang,span,mat):
        # Scallop with a genuine fluted double-curved surface and ribbed lip.
        sa,ca = math.sin(ang),math.cos(ang)
        nt,ns = 5+2*self.d,18+6*self.d
        rows, lip = [], []
        for i in range(nt+1):
            t=i/nt
            row=[]
            for j in range(ns+1):
                s=2*j/ns-1
                angle=s*1.13
                rib=(1+math.cos(s*7*math.pi))/2
                radius=span*(.13+.87*t)*(1-.10*s*s+.055*rib*t**3)
                a,b=radius*math.sin(angle),radius*math.cos(angle)-span*.13
                z = 10 + span*(.19*(1-s*s)*math.sin(math.pi*.88*t)+.073*rib*t+.038*(1-t))
                row.append((x+ca*a-sa*b,y+sa*a+ca*b,z))
            rows.append(row)
        self.sheet(mat,rows,max(1.1,.055*span))
        lip=[(u,v,h+.1) for u,v,h in rows[-1]]
        self.tube(self.trim,lip,span*.026,.74,sides=5)
        for j in range(0,ns+1,max(1,ns//7)):
            self.tube(self.trim,[r[j] for r in rows],max(.65,span*.017),.7,sides=4)

    def rosette(self,x,y,size,n,phase=0,mat=None):
        for j in range(n):
            a=phase+2*math.pi*j/n
            self.leaf(x+size*.13*math.cos(a),y+size*.13*math.sin(a),a,size*.84,
                      size*.76/n, .12*size,12,mat or self.light,False)
        if self.d>1:
            for j in range(n):
                a=phase+math.pi*(2*j+1)/n
                self.leaf(x,y,a,.50*size,.52*size/n,-size*.05,15,self.main,False)
        self.pearl(x,y,17,.16*size,self.trim)

    def scroll(self,x,y,a,size,hand=1,rich=True):
        """A single continuous C-scroll with sprouting acanthus and a turned eye."""
        ca,sa = math.cos(a), math.sin(a)
        def mapped(u,v):
            return x+size*(ca*u-sa*hand*v), y+size*(sa*u+ca*hand*v)
        ctrl = ((0,0),(.19,-.14*self.stretch),(.39,.30),(.61,.30))
        count = 10+3*self.d
        path,rr=[],[]
        for i in range(count+1):
            t=i/count
            px,py=mapped(*_palace_bezier(ctrl,t))
            path.append((px,py,8.5+4*t))
            rr.append(size*(.026+.023*math.sin(math.pi*t*.72)))
        terminal = 14+6*self.d
        for j in range(1,terminal+1):
            t=j/terminal
            phi=-math.pi/2+2*math.pi*self.turns*t
            r=.205*math.exp(-2.45*t)
            px,py=mapped(.61+r*math.cos(phi),.505+r*math.sin(phi))
            path.append((px,py,12.5+3*t))
            rr.append(size*(.045*(1-t)**.81+.005))
        self.tube(self.stem,path,rr,.78)
        if self.d>1:
            line=[(u,v,h+rad*.71) for (u,v,h),rad in zip(path,rr)]
            self.tube(self.trim,line,[max(.32,.16*r) for r in rr],.72,sides=4)
        if rich:
            n=1+int(2.2*self.leafiness)+int(self.d==3)
            for j in range(n):
                t=(j+.7)/(n+.63)
                p=_palace_bezier(ctrl,t)
                q=_palace_bezier(ctrl,min(1,t+.01))
                dx,dy=q[0]-p[0],q[1]-p[1]
                b=math.atan2(dy,dx)+(.57 if j%2==0 else -.77)
                px,py=mapped(*p)
                self.leaf(px,py,a+hand*b,size*(.22+.09*math.sin(math.pi*t)),
                          size*.044,hand*size*(.085 if j%2==0 else -.096),
                          10,self.light)
        px,py,_=path[-1]
        self.pearl(px,py,15,size*.022,self.trim)

    def ring(self,scale=1):
        n = 64 + self.d*32
        return [(self.a*x*scale,self.b*y*scale) for x,y in
                (panel_outline(self.shape,i/n) for i in range(n))]

    def mount(self):
        pts=self.ring()
        n=len(pts)
        vv=[(x,y,1.4) for x,y in pts]+[(x,y,-.7) for x,y in pts]
        vv.extend(((0,0,1.4),(0,0,-.7)))
        ff=[]
        for i in range(n):
            j=(i+1)%n
            ff.extend(((2*n,i,j),(2*n+1,n+j,n+i),(i,i+n,j+n,j)))
        self.emit("fresco" if self.painted else "ground",vv,ff)
        # A guilloche/profile is inset by a fixed distance all round, including on long panels.
        seq = ((-6,5,4,"shadow"),(1,8.6,7,self.light),(11,3.4,9,self.trim),
               (18,4.2,5,self.main))
        for shift,r,z,mat in seq:
            path=[]
            for i,(x,y) in enumerate(pts):
                ax,ay=pts[(i-1)%n]
                bx,by=pts[(i+1)%n]
                dx,dy=bx-ax,by-ay
                mag=math.hypot(dx,dy)
                path.append((x-shift*dy/mag,y+shift*dx/mag,z))
            self.tube(mat,path,r,.82,True)
        if "beads" in self.elements and self.d>1:
            # Arc-length sampling avoids bunching beads on rounded rectangular corners.
            lengths=[math.hypot(pts[(i+1)%n][0]-p[0],pts[(i+1)%n][1]-p[1]) for i,p in enumerate(pts)]
            total=sum(lengths)
            count=max(12,min(118,int(total/32)))
            i=0
            start=0
            for j in range(count):
                target=total*(j+.5)/count
                while i<n-1 and start+lengths[i]<target:
                    start+=lengths[i]
                    i+=1
                f=(target-start)/lengths[i]
                p,q=pts[i],pts[(i+1)%n]
                dx,dy=q[0]-p[0],q[1]-p[1]
                x,y=p[0]+f*dx,p[1]+f*dy
                self.pearl(x-15*dy/lengths[i],y+15*dx/lengths[i],8.1,2.45,self.trim)

    def collar(self,x,y,rad,sides):
        # A lozenge setting with a stepped, bevelled edge.
        vv=[]
        for size,z in ((1,2),(.97,9),(.77,14)):
            for j in range(sides):
                a=2*math.pi*j/sides
                vv.append((x+rad*size*.78*math.cos(a),y+rad*size*math.sin(a),z))
        ff=[]
        for i in range(sides):
            j=(i+1)%sides
            ff.extend(((i,j,j+sides,i+sides),(i+sides,j+sides,j+2*sides,i+2*sides)))
        for k in range(1,sides-1):
            ff.extend(((0,k+1,k),(2*sides,2*sides+k,2*sides+k+1)))
        self.emit(self.main,vv,ff)

    def focal(self,x,y,size,motif):
        if motif=="shell":
            self.scallop(x,y-size*.42,0,size*1.13,self.light)
        elif motif=="flower":
            self.rosette(x,y,size,8,self.phase)
        elif motif=="sunburst":
            nr=12+4*(self.d>1)
            for j in range(nr):
                a=2*math.pi*j/nr
                k=.98 if j%2==0 else .72
                self.leaf(x,y,a,size*k,size*.069,size*.05,10,
                          self.main if j%2==0 else self.light,False)
            self.rosette(x,y,.40*size,8,self.phase,self.trim)
        else:
            for hand in (-1,1):
                self.scroll(x,y-size*.61,math.pi/2-hand*.34,size*1.24,hand)
            self.leaf(x,y-size*.44,math.pi/2,.96*size,.12*size,0,13,self.main)

    def side_work(self):
        a,b = self.a,self.b
        # The frame-side scale is capped by the shortest dimension.
        S=min(a,b)
        if self.style=="bavarian":
            for sign in (-1,1):
                y=sign*.77*b
                span=S*.40*self.stretch
                for hand in (-1,1):
                    ang=0 if hand==1 else math.pi
                    self.scroll(0,y,ang-.11*sign*hand,span,-sign*hand)
                    if "spray" in self.elements or self.leafiness>.62:
                        self.scroll(hand*.48*span,y-sign*.08*span,ang-.82*sign*hand,
                                    .56*span,sign*hand,self.d>1)
                if "shell" in self.elements or "fan" in self.elements:
                    self.scallop(0,y,0 if sign<0 else math.pi,.29*span,self.light)
            for sign in (-1,1):
                self.scroll(sign*.82*a,-.09*b,math.pi/2+.26*sign,.39*S,sign)
                if self.d>=2:
                    self.scroll(sign*.82*a,-.09*b,-math.pi/2-.16*sign,.30*S,-sign)
        elif self.style=="russian":
            for sign in (-1,1):
                y=sign*.76*b
                for hand in (-1,1):
                    self.scroll(0,y,0 if hand>0 else math.pi,.49*S,-sign*hand)
                    px=hand*.30*S
                    self.leaf(px,y-sign*.14*S,(.24*math.pi if hand>0 else .76*math.pi)*(-sign),
                              .24*S,.033*S,hand*sign*.059*S,11,self.main)
                if "rosette" in self.elements:
                    self.rosette(0,y,.078*S,7,0)
            for hand in (-1,1):
                x=hand*a*.83
                for tier in range(2+self.d//2):
                    y=(.31-tier*.26)*b
                    self.scroll(x,y,-math.pi/2+hand*.17,.22*S,hand,self.d>1)
                    self.leaf(x,y-.085*S,-math.pi/2-hand*.26,.14*S,.024*S,
                              hand*.055*S,8,self.light)
        else:
            for hand in (-1,1):
                x=hand*.79*a
                for j in range(3):
                    y=(.45-j*.40)*b
                    r=S*(.092 if j==1 else .07)
                    self.collar(x,y,r,4)
                    self.rosette(x,y,.79*r,6,self.phase,self.light)
                    for s in (-1,1):
                        self.leaf(x,y+s*r*.89,s*math.pi/2,
                                  .104*S,.019*S,hand*.027*S,8,self.trim)
            for sign in (-1,1):
                y=sign*.74*b
                for hand in (-1,1):
                    self.scroll(0,y,0 if hand>0 else math.pi,.48*S,-sign*hand)
                self.collar(0,y,.076*S,8)
                if "rosette" in self.elements or "spray" in self.elements:
                    self.rosette(0,y,.065*S,6,0)

    def wreath(self):
        # Measure the perimeter so leaves retain their scale on long wall panels.
        a,b=self.a,self.b
        contour=[panel_outline(self.shape,i/192) for i in range(192)]
        scale=(.84 if self.painted else .79) if self.ultra else (.88 if self.painted else .84)
        contour=[(a*u*scale,b*v*scale) for u,v in contour]
        cumulative=[0.]
        for i,(u,v) in enumerate(contour):
            x,y=contour[(i+1)%len(contour)]
            cumulative.append(cumulative[-1]+math.hypot(x-u,y-v))
        import bisect
        total=cumulative[-1]
        count=min(36,max(8,round(total/(97 if self.style=="mexican" else 121))))
        count=2*max(4,round(count*(.62+.43*self.leafiness)/2))
        def point(t):
            s=(t%1)*total
            i=min(len(contour)-1,bisect.bisect_right(cumulative,s)-1)
            u,v=contour[i];x,y=contour[(i+1)%len(contour)]
            dx,dy=x-u,y-v; d=cumulative[i+1]-cumulative[i]
            k=(s-cumulative[i])/d
            inset=(7+10*math.sin(t*count*math.pi*2))*(.55+self.curl*.7)
            return u+k*dx-inset*dy/d,v+k*dy+inset*dx/d
        n=count*(5+self.d)
        ridge=[(*point(i/n),8.) for i in range(n)]
        self.tube(self.trim,ridge,6.8 if self.ultra else 3.8,.82,True)
        if self.ultra:
            backing=[(x*1.027,y*1.027,3.) for x,y,_ in ridge]
            self.tube(self.light,backing,12,.60,True)
        spread=1.46 if self.ultra else 1.
        for j in range(count):
            t=(j+.5)/count;x,y=point(t)
            x1,y1=point(t+.002);angle=math.atan2(y1-y,x1-x)
            for side in (-1,1):
                self.leaf(x,y,angle+side*.49,spread*(40+15*self.leafiness),spread*(7+3*self.leafiness),
                          side*13,10 if self.ultra else 8,self.light if (j%3 or side<0) else self.trim)
            if self.d>1 and (j%3==0 or self.style=="mexican" and j%2==0):
                self.rosette(x,y,spread*13.5,5,self.phase,self.trim)

    def decorate(self):
        self.mount()
        if self.d>=2 and self.leafiness>.16:self.wreath()
        self.side_work()
        if self.ultra and self.d>=2:self.interlaced_relief()
        if self.open_center or self.painted:
            return
        S=min(self.a,self.b)
        span=S*(.48 if self.style=="bavarian" else .53)
        # A frame around the focal motif carries reflected broken scrolls or the stepped
        # diamond system. Motif and frame can therefore be recombined independently.
        if self.style=="russian":
            for hand in (-1,1):
                for sign in (-1,1):
                    a=(math.pi/2-.46*hand)*sign
                    self.scroll(hand*.075*span,sign*.24*span,a,span*1.08,hand*sign)
        elif self.style=="mexican":
            for hand in (-1,1):
                self.scroll(hand*.25*span,-.31*span,math.pi/2-hand*.71,1.28*span,hand)
            for sign in (-1,1):
                self.collar(0,sign*span*.87,span*.23,4)
        else:
            for hand in (-1,1):
                self.scroll(hand*.08*span,-.42*span,math.pi/2-hand*.79,1.16*span,hand)
                if "spray" in self.elements:
                    self.scroll(hand*.50*span,.25*span,math.pi/2-hand*.24,.59*span,-hand)
        self.focal(0,0,span*.71,self.motif)

    def interlaced_relief(self):
        """Bridge the gaps between the focal piece and its framing frieze."""
        S=min(self.a,self.b)
        if S<235:return
        scl=min(1.,.56+.55*self.leafiness)
        lace=self.ultra["lace"]
        if self.painted:
            # Preserve the centre of the painting and mask its margin with acanthus.
            sites=(.05,.12,.2,.30,.38,.45,.55,.62,.7,.80,.88,.95)
            for t in sites:
                u,v=panel_outline(self.shape,t)
                x,y=.82*self.a*u,.82*self.b*v
                a=math.atan2(self.b*v,self.a*u)+math.pi/2
                for i in (-1,1):
                    self.scroll(x,y,a if i>0 else a+math.pi,.15*S*scl,i,False)
            return
        vertical=self.b>=self.a
        long,short=(self.b,self.a) if vertical else (self.a,self.b)
        n=self.ultra["tiers"]
        for k in range(n):
            t=(k+1)/(n+1)
            for hemisphere in (-1,1):
                u=hemisphere*long*(.24+.40*t)
                for hand in (-1,1):
                    v=hand*short*(.15+.17*t)
                    x,y=(v,u) if vertical else (u,v)
                    angle=(math.pi/2 if vertical else 0)+(math.pi if hemisphere<0 else 0)
                    angle+=hand*hemisphere*(.7+.19*t)
                    span=S*(.29-.09*t)*scl
                    if lace=="fan" and k%2==1:
                        self.scallop(x,y,angle-math.pi/2,span*.65,self.main)
                    else:
                        self.scroll(x,y,angle,span,hand,lace=="spray")
                        self.leaf(x,y,angle+.75*hand,span*.82,span*.14,hand*span*.22,12,self.light)
                if k%2==1:
                    x,y=(0,u) if vertical else (u,0)
                    self.rosette(x,y,S*.059,7,self.phase,self.trim)


def decorate_panel(geom, zone, frame, width, height, style, detail, relief, seed, recipe):
    """Build a closed field plate, mouldings and carved relief in the supplied plane."""
    if width <= 0 or height <= 0:
        return
    panel = _PalacePanel(geom,zone,frame,width,height,style,detail,relief,seed,recipe)
    panel.decorate()
