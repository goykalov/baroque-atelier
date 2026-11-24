import threading
import scriptcontext as sc
from System.Windows.Forms import Timer


node = ghenv.Component
doc = node.OnPingDocument()
state = sc.sticky.setdefault(("palace-ultra-editor", doc.RuntimeID, str(node.InstanceGuid)),
                             {"pressed": False, "busy": False, "message": "Готово к работе"})
down = str(fresh).lower() == "true"
if down and not state["pressed"] and not state["busy"]:
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
    outcome = {}
    state.update(busy=True, message="Подбирается новая композиция")

    def work():
        try:
            if atelier:
                outcome["plan"]=search_hall(text,school,budget=count,history=history,backend=engine,
                                             size_m=measurements,progress=lambda msg:outcome.update(progress=msg))
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
        state["busy"] = False
        if node.OnPingDocument() != doc:
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
                if report:state["message"]+=" · Qwen: "+str(report["ai_passes"])+" проходов"
            except Exception as error:
                state["message"] = "Ошибка · " + str(error)
            node.ExpireSolution(False)

        doc.ScheduleSolution(20, commit)

    timer = Timer()
    timer.Interval = 160
    timer.Tick += tick
    timer.Start()
    state["timer"] = timer
    threading.Thread(target=work, daemon=True).start()
state["pressed"] = down
status = state["message"]
