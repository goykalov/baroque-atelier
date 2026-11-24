import base64
import System
import Rhino
import Rhino.Geometry as G
from System.Drawing import Color
from Rhino.DocObjects import Layer, Material, ObjectAttributes, ObjectColorSource, ObjectEnumeratorSettings, ObjectMaterialSource


def room_transform(rd, size, shape):
    unit=Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters,rd.ModelUnitSystem)
    plane=G.Plane.WorldXY
    if shape is not None:
        if isinstance(shape,G.Box): shape=shape.ToBrep()
        if not isinstance(shape,G.Brep) or not shape.IsSolid or shape.Vertices.Count!=8 or shape.Faces.Count!=6:
            raise ValueError("Объём комнаты должен быть прямоугольным замкнутым Brep")
        pts=[v.Location for v in shape.Vertices]
        bottom=min(p.Z for p in pts); top=max(p.Z for p in pts)
        tol=max(rd.ModelAbsoluteTolerance,unit*.1)*2
        floor=[p for p in pts if abs(p.Z-bottom)<tol]
        if len(floor)!=4 or any(not any(abs(q.Z-top)<tol and math.hypot(p.X-q.X,p.Y-q.Y)<tol for q in pts) for p in floor):
            raise ValueError("У объёма должны быть горизонтальный пол и вертикальные стены")
        near=sorted(floor[1:],key=lambda q:q.DistanceTo(floor[0]))
        u,v=near[1]-floor[0],near[0]-floor[0]
        size=(u.Length/unit,v.Length/unit,(top-bottom)/unit)
        u.Unitize(); v.Unitize()
        if abs(u*v)>.0001 or (floor[0]+u*(size[0]*unit)+v*(size[1]*unit)).DistanceTo(near[2])>tol:
            raise ValueError("Нужен прямоугольный план")
        if G.Vector3d.CrossProduct(u,v).Z<0:v.Reverse()
        plane=G.Plane(G.Point3d(sum(p.X for p in floor)/4,sum(p.Y for p in floor)/4,bottom),u,v)
    return size,G.Transform.PlaneToPlane(G.Plane.WorldXY,plane)*G.Transform.Scale(G.Point3d.Origin,unit)


def palace_bytes(data):
    return System.Convert.FromBase64String(base64.b64encode(data).decode("ascii"))


def room_meshes(raw,style,placement,scan=None,painting_path=None):
    assembly=next((a for a in System.AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name=="PalaceBuffers"),None)
    if assembly is None:assembly=System.Reflection.Assembly.Load(System.Convert.FromBase64String(PALACE_DLL))
    make=assembly.GetType("PalaceBuffers").GetMethod("MeshFromBuffers")
    meshes=[];materials=[];keys=[]
    textures=painting_path if isinstance(painting_path,dict) else {"fresco":painting_path}
    def add(m,zone,mat):
        painted=mat.startswith("fresco")
        if painted:
            bb=m.GetBoundingBox(True)
            w,h=bb.Max.X-bb.Min.X,bb.Max.Y-bb.Min.Y
            for vert in m.Vertices:
                u,v=palace_uv(mat,(vert.X-bb.Min.X)/w,(bb.Max.Y-vert.Y)/h,w,h) if "palace_uv" in globals() else ((vert.X-bb.Min.X)/w,(bb.Max.Y-vert.Y)/h)
                m.TextureCoordinates.Add(u,v)
        m.Transform(placement)
        if not m.IsValid:raise ValueError("Некорректная сетка · "+zone+" / "+mat)
        col=Color.FromArgb(*( (255,255,255) if painted and textures.get(mat) else ROOM_PALETTES[style][mat] ))
        material=Rhino.Display.DisplayMaterial(col)
        if textures.get(mat):material.SetBitmapTexture(str(textures[mat]),True)
        material.Shine=75 if mat=="gold" else 18
        if mat=="glass":material.Transparency=.80
        if mat=="gold":material.Specular=Color.FromArgb(239,209,143)
        meshes.append(m);materials.append(material);keys.append(zone+" / "+mat)
    for (zone,mat),(v,t) in raw.parts.items():
        m=make.Invoke(None,System.Array[System.Object]([palace_bytes(v),palace_bytes(t)]))
        add(m,zone,mat)
    if scan is not None:
        if not isinstance(scan,G.Mesh) or not scan.IsValid:raise ValueError("Выберите Mesh для оконной резьбы")
        bb=scan.GetBoundingBox(True); dx=bb.Max.X-bb.Min.X;dy=bb.Max.Y-bb.Min.Y
        if min(dx,dy)<=0:raise ValueError("Расположите наличник в плоскости XY")
        for idx,(frame,w,h) in enumerate(raw.windows):
            scale=min(w*1.15/dx,h*1.15/dy)
            a=G.Point3d(*frame(0,0,0)); u=G.Point3d(*frame(1,0,0))-a;v=G.Point3d(*frame(0,1,0))-a
            tf=G.Transform.PlaneToPlane(G.Plane.WorldXY,G.Plane(a,u,v))*G.Transform.Scale(G.Point3d.Origin,scale)*G.Transform.Translation(-bb.Center.X,-bb.Center.Y,-bb.Min.Z)
            m=scan.DuplicateMesh();m.Transform(tf);add(m,"Наличник "+str(idx+1),"plaster")
    return meshes,materials,keys


def palace_camera(rd,size,tf):
    L,W,H=size
    def point(x,y,z):
        p=G.Point3d(x,y,z);p.Transform(tf);return p
    vp=rd.Views.ActiveView.ActiveViewport
    vp.ChangeToPerspectiveProjection(True,19)
    vp.SetCameraLocations(point(-L*.20,-W*.22,H*.64),point(L*.39,W*.34,H*.32))
    vp.CameraUp=G.Vector3d.ZAxis
    rd.Views.Redraw()


def palace_objects(rd, owner):
    options = ObjectEnumeratorSettings()
    options.HiddenObjects = True
    options.LockedObjects = True
    return list(rd.Objects.FindByUserString("PalaceUltra.Owner", owner, True, False, True, options) or ())


def publish_palace(rd, owner, stamp, batch, painting_path):
    previous = palace_objects(rd, owner)
    meshes, materials, parts = batch
    if len(previous) == len(meshes) and all(o.Attributes.GetUserString("PalaceUltra.State") == stamp for o in previous):
        return
    def material_name(key,appearance):
        return ("Барочная мастерская · "+key+" · "+str(appearance.Diffuse.ToArgb())+
                " · t"+str(round(appearance.Transparency,2)))
    old_by_name={obj.Attributes.Name:obj for obj in previous}
    retained=set()
    pending=[]
    for mesh,appearance,part in zip(meshes,materials,parts):
        old=old_by_name.get(part)
        _,key=part.split(" / ")
        index=old.Attributes.MaterialIndex if old is not None else -1
        if (old is not None and index>=0 and rd.Materials[index].Name==material_name(key,appearance)
                and old.Geometry.DataCRC(0)==mesh.DataCRC(0)):
            retained.add(old.Id)
        else:
            pending.append((mesh,appearance,part))
    retiring=[obj for obj in previous if obj.Id not in retained]
    if any(obj.IsLocked for obj in retiring):
        raise ValueError("Снимите блокировку с объектов редактируемой зоны")
    if not pending and not retiring:
        return
    prefix = "Барочная мастерская · " + owner[:8]
    layers, material_ids = {}, {}
    textures=painting_path if isinstance(painting_path,dict) else {"fresco":painting_path}
    added, deleted = [], []
    undo = rd.BeginUndoRecord("Барочная мастерская")
    try:
        for mesh, appearance, part in pending:
            zone, key = part.split(" / ")
            if zone not in layers:
                label = prefix + " · " + zone
                layer = rd.Layers.FindName(label)
                if layer is None:
                    layer = Layer()
                    layer.Name = label
                    layers[zone] = rd.Layers.Add(layer)
                else:
                    layers[zone] = layer.Index
            if key not in material_ids:
                color = appearance.Diffuse
                label = material_name(key,appearance)
                item = next((m for m in rd.Materials if not m.IsDeleted and m.Name == label), None)
                if item is None:
                    item = Material()
                    item.Name = label
                    item.DiffuseColor = color
                    item.Shine = appearance.Shine
                    item.Transparency = appearance.Transparency
                    item.SpecularColor = appearance.Specular
                    if textures.get(key):
                        item.SetBitmapTexture(str(textures[key]))
                    material_ids[key] = rd.Materials.Add(item)
                else:
                    material_ids[key] = item.MaterialIndex
            attr = ObjectAttributes()
            attr.Name = part
            attr.LayerIndex = layers[zone]
            attr.ObjectColor = appearance.Diffuse
            attr.ColorSource = ObjectColorSource.ColorFromObject
            attr.MaterialIndex = material_ids[key]
            attr.MaterialSource = ObjectMaterialSource.MaterialFromObject
            attr.SetUserString("PalaceUltra.Owner", owner)
            attr.SetUserString("PalaceUltra.State", stamp)
            obj_id = rd.Objects.AddMesh(mesh, attr)
            if obj_id == System.Guid.Empty:
                raise ValueError("Не удалось добавить «" + part + "»")
            added.append(obj_id)
        for obj in retiring:
            if not rd.Objects.Delete(obj.Id, True):
                raise ValueError("Не удалось заменить «" + obj.Name + "»")
            deleted.append(obj.RuntimeSerialNumber)
    except Exception:
        for serial in deleted:
            rd.Objects.Undelete(serial)
        for obj_id in added:
            rd.Objects.Delete(obj_id, True)
        raise
    finally:
        if undo:
            rd.EndUndoRecord(undo)
    rd.Views.Redraw()
