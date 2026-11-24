import threading
import scriptcontext as sc
from System.Windows.Forms import Timer


node = ghenv.Component
doc = node.OnPingDocument()
state = sc.sticky.setdefault(("palace-ultra-editor", doc.RuntimeID, str(node.InstanceGuid)),
                             {"pressed": False, "busy": False, "message": "Готово к работе"})
down = str(fresh).lower() == "true"
edit_down = str(globals().get("edit_zone","")).lower() == "true"
finish_down = str(globals().get("finish_search","")).lower() == "true"
if finish_down and not state.get("finish_pressed") and state["busy"]:
    state["finish"].set()
    state["message"]="Выбран лучший найденный вариант"
start_new=down and not state["pressed"]
start_edit=edit_down and not state.get("edit_pressed") and not start_new
if (start_new or start_edit) and not state["busy"]:
    shelf = next(o for o in doc.Objects if o.NickName == "Рецепт текущего зала")
    saved = shelf.UserText
    previous = json.loads(saved).get("plan")
    text, engine, school = str(prompt or "").strip(), str(backend), str(style)
    atelier=bool(globals().get("_PALACE_ARCHITECTURE_RELEASE"))
    state_json=json.loads(saved)
    count=int(float(trials))
    history=state_json.get("history",[]) if atelier else []
    if atelier and previous:
        history=(history+[hall_history_item(previous)])[-12:]
    measurements=(float(plan_length)/1000,float(plan_width)/1000,float(plan_height)/1000) if "plan_length" in globals() else None
    # The single button starts a fresh composition even when prompt and style stay fixed.
    done = threading.Event()
    finish_signal = threading.Event()
    outcome = {}
    target=str(globals().get("edit_scope","ceiling")) if start_edit else "hall"
    state.update(busy=True, finish=finish_signal, message="Подбирается композиция")

    def work():
        try:
            if atelier:
                options=dict(budget=count,backend=engine,size_m=measurements,finish=finish_signal.is_set,
                             progress=lambda msg:outcome.update(progress=msg))
                if target=="hall":
                    outcome["plan"]=search_hall(text,school,history=history,**options)
                else:
                    if previous is None:
                        raise ValueError("Сначала создайте зал кнопкой «Найти новый зал»")
                    outcome["plan"]=edit_hall_zone(previous,target,text,**options)
            else:
                opts={"dense":True} if globals().get("_PALACE_DENSE_RELEASE") else {}
                outcome["plan"]=new_ultra_plan(text,school,avoid=previous,backend=engine,attempts=count,**opts)
        except Exception as error:
            outcome["error"] = str(error)
        finally:
            done.set()

    def tick(sender, args):
        if not done.is_set():
            progress=outcome.get("progress")
            if progress and state["message"]!=progress and node.OnPingDocument()==doc:
                state["message"]=progress
                doc.ScheduleSolution(20,lambda d:node.ExpireSolution(False))
            return
        timer.Stop()
        timer.Dispose()
        state.pop("timer", None)
        if node.OnPingDocument() != doc:
            state["busy"] = False
            return

        def commit(d):
            try:
                if "error" in outcome:
                    raise ValueError(outcome["error"])
                if shelf.UserText != saved:
                    raise ValueError("Рецепт был изменён во время генерации")
                result = outcome["plan"]
                shelf.UserText = json.dumps({"plan": result, "history":history}, ensure_ascii=False)
                shelf.ExpireSolution(False)
                d.Modified()
                report=result.get("search")
                state["message"] = "Рецепт готов · " + result["title"]
                if report:
                    state["message"]+=" · Qwen: "+str(report["ai_passes"])+" проходов"
                    if report.get("geometry_passes"):
                        state["message"]+=" · слоёв рельефа: "+str(report["geometry_passes"])
            except Exception as error:
                state["message"] = "Ошибка · " + str(error)
            state["busy"] = False
            state.pop("finish",None)
            node.ExpireSolution(False)

        doc.ScheduleSolution(20, commit)

    timer = Timer()
    timer.Interval = 160
    timer.Tick += tick
    timer.Start()
    state["timer"] = timer
    threading.Thread(target=work, daemon=True).start()
state["pressed"] = down
state["edit_pressed"] = edit_down
state["finish_pressed"] = finish_down
status = state["message"]
