import System
import Grasshopper as gh
from Grasshopper.Kernel import GH_ParameterSide
from Grasshopper.Kernel.Special import GH_NumberSlider
from System.Drawing import PointF

def dial(doc,name,value,low,high,x,y):
    s=GH_NumberSlider()
    s.NickName=name
    s.Slider.Maximum=System.Decimal(high)
    s.Slider.Minimum=System.Decimal(low)
    s.Slider.DecimalPlaces=0
    s.SetSliderValue(System.Decimal(value))
    s.CreateAttributes();s.Attributes.Pivot=PointF(x,y)
    doc.AddObject(s,False)
    return s

def python_node(doc,name,src,inputs,output,x,y,optional=False):
    c=gh.Instances.ComponentServer.EmitObject(System.Guid("719467e6-7cf5-4848-99b0-c5dd57e5442c"))
    c.CreateAttributes();c.UsingStandardOutputParam=False;c.MarshGuids=False;c.MarshInputs=True;c.MarshOutputs=True
    for p in list(c.Params.Input): c.Params.UnregisterInputParameter(p)
    for p in list(c.Params.Output): c.Params.UnregisterOutputParameter(p)
    for i,(label,source) in enumerate(inputs):
        p=c.CreateParameter(GH_ParameterSide.Input,i);p.Name=p.NickName=label;p.Optional=optional
        c.Params.RegisterInputParam(p)
        if source is not None:p.AddSource(source)
    p=c.CreateParameter(GH_ParameterSide.Output,0);p.Name=p.NickName=output;c.Params.RegisterOutputParam(p)
    c.VariableParameterMaintenance();c.NickName=name;c.SetSource(src)
    c.Attributes.Pivot=PointF(x,y);doc.AddObject(c,False)
    return c

def crest(doc,group,kind,common):
    if kind=="SHELL":
        first=("Рёбра раковины",11,5,19)
        second=("Раскрытие раковины",112,75,155)
        label="Раковина"
    else:
        first=("Листья пальметты",9,5,15)
        second=("Размах пальметты",100,60,150)
        label="Пальметта"
    n=dial(doc,*first,300,330)
    a=dial(doc,*second,300,385)
    script="kind="+repr(kind)+"\n"+crown_code
    obj=python_node(doc,label,script,common+[("count",n),("opening",a)],"geometry",680,325)
    for o in (n,a,obj):group.AddObject(o.InstanceGuid)
    return obj
