"""Russian desktop front end to the standard-library OBJ and recipe exporter."""
import argparse
from datetime import datetime
import os
from pathlib import Path
import queue
import secrets
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from uuid import uuid4

from palace_free import export, read_recipe
from palace_plan import native_available


SCHOOLS = {"Случайная школа":"random", "Баварский рокайль":"bavarian", "Русское елизаветинское барокко":"russian",
           "Новоиспанское барокко Мексики":"mexican"}
ENGINES = {"Локальная Qwen":"native", "Автономные правила":"rules"}
if not native_available():
    ENGINES.pop("Локальная Qwen")
QUALITIES = {"Эскиз":1,"Проработка":2,"Тонкая резьба":3}
BUDGETS={"До 1 минуты":60,"До 10 минут":600,"До 1 часа":3600}
def _key(mapping,value):
    return next((k for k,v in mapping.items() if v==value),next(iter(mapping)))


def _number(value):
    return float(value.strip().replace(",","."))


class Workshop:
    def __init__(self,root):
        self.root = root
        self.project = None
        self.busy = False
        self.events = queue.SimpleQueue()
        self.worker = None
        self.atelier=os.environ.get("BAROQUE_ATELIER")=="1"
        self.dense=self.atelier or os.environ.get("BAROQUE_DENSE")=="1"
        self.finish_event=threading.Event()
        title="Ателье барокко" if self.atelier else "Ветвящийся зал" if self.dense else "Барочная мастерская"
        root.title(title)
        root.minsize(690,365)
        root.columnconfigure(0,weight=1)
        root.rowconfigure(0,weight=1)
        self.form = form = ttk.Frame(root,padding=(22,13,22,14))
        form.grid(sticky="nsew")
        for i in range(3):
            form.columnconfigure(i, weight=1,uniform="fields")
        form.rowconfigure(6,weight=1)
        self.school = tk.StringVar(value=next(iter(SCHOOLS)))
        self.engine = tk.StringVar(value=next(iter(ENGINES)))
        self.quality = tk.StringVar(value="Тонкая резьба")
        self.drafts = tk.IntVar(value=2)
        self.budget=tk.StringVar(value=next(iter(BUDGETS)))
        self.seed = tk.StringVar()
        self.size = [tk.StringVar(value=x) for x in (("12","8,5","6,8") if self.dense else ("9","6,7","4,9"))]
        self.tuning = [tk.StringVar(value=x) for x in ("1,3","0","0")]
        self.folder = tk.StringVar(value=str(Path(__file__).resolve().parent/("Ателье · мои залы" if self.atelier else "Мои залы")))
        self.scan = tk.StringVar()
        self.painting = tk.BooleanVar(value=True)
        self.project_title = tk.StringVar(value="Новый проект")
        self.status = tk.StringVar(value="Готово к работе")
        self.advanced=tk.BooleanVar(value=False)
        ttk.Label(form,text=title,
                  font=("Segoe UI",18,"bold")).grid(row=0,column=0,columnspan=2,sticky="w")
        self.open_button = ttk.Button(form,text="Открыть рецепт…",command=self.load)
        self.open_button.grid(row=0,column=2,sticky="e")
        ttk.Label(form,textvariable=self.project_title,wraplength=650).grid(row=1,column=0,columnspan=3,sticky="w",pady=(2,8))
        for col,(title,val,items) in enumerate((("Школа",self.school,SCHOOLS),("Генератор композиции",self.engine,ENGINES),
                                                 ("Детализация геометрии",self.quality,QUALITIES))):
            part=self.cell(2,col,title)
            ttk.Combobox(part,textvariable=val,values=tuple(items),state="readonly",width=22).pack(fill="x")
        for col,(title,var) in enumerate(zip(("Длина, м","Ширина, м","Высота, м"),self.size)):
            ttk.Entry(self.cell(3,col,title),textvariable=var,width=10).pack(fill="x")
        field_header=ttk.Frame(form)
        field_header.grid(row=5,column=0,columnspan=3,sticky="ew",pady=(4,2))
        ttk.Label(field_header,text="Описание · оставьте пустым для случайного зала",font=("Segoe UI",10,"bold")).pack(side="left")
        ttk.Checkbutton(field_header,text="Настройки",variable=self.advanced,command=self.toggle_settings).pack(side="right",padx=8)
        self.prompt=tk.Text(form,height=4,width=54,wrap="word",font=("Segoe UI",10),padx=6,pady=5,undo=True)
        self.prompt.grid(row=6,column=0,columnspan=3,sticky="nsew")
        for col,(title,var,lo,hi) in enumerate(zip(("Глубина рельефа ×","Поправка листвы","Поправка позолоты"),
                                                    self.tuning,(.35,-1,-1),(2,1,1))):
            ttk.Spinbox(self.cell(7,col,title),textvariable=var,from_=lo,to=hi,increment=.05,width=10).pack(fill="x")
        ttk.Spinbox(self.cell(8,0,"Эскизов для отбора"),textvariable=self.drafts,from_=1,to=4,width=10).pack(fill="x")
        ttk.Entry(self.cell(8,1,"Число варианта · можно пропустить"),textvariable=self.seed,width=14).pack(fill="x")
        scan_box=self.cell(8,2,"Наличник из OBJ")
        self.scan_label=tk.StringVar(value="Встроенный")
        ttk.Button(scan_box,textvariable=self.scan_label,command=self.set_scan).pack(side="left",fill="x",expand=True)
        ttk.Button(scan_box,text="×",width=3,command=lambda:self.set_scan_value("")).pack(side="right")
        dest=ttk.Frame(form)
        dest.grid(row=9,column=0,columnspan=3,sticky="ew",pady=(7,4))
        dest.columnconfigure(1,weight=1)
        ttk.Label(dest,text="Папка результатов").grid(row=0,column=0,padx=(0,6))
        ttk.Entry(dest,textvariable=self.folder).grid(row=0,column=1,sticky="ew")
        ttk.Button(dest,text="Выбрать…",command=self.choose_folder).grid(row=0,column=2,padx=(5,0))
        actions=ttk.Frame(form)
        actions.grid(row=10,column=0,columnspan=3,sticky="ew",pady=(8,2))
        ttk.Style().configure("Generate.TButton",font=("Segoe UI",11,"bold"),padding=(11,7))
        self.new_button=ttk.Button(actions,text="Новый ветвящийся зал" if self.dense else "Новый пышный зал",
                                   style="Generate.TButton",command=lambda:self.start(False))
        if self.atelier:
            self.new_button.configure(text="Найти новый зал")
        self.new_button.pack(side="left",padx=(0,5))
        self.edit_button=ttk.Button(actions,text="Применить к открытому проекту",command=lambda:self.start(True),state="disabled")
        self.edit_button.pack(side="left")
        ttk.Button(actions,text="Открыть папку",command=self.reveal).pack(side="right")
        if self.atelier:
            bar=ttk.Frame(form)
            bar.grid(row=13,column=0,columnspan=3,sticky="ew",pady=(8,2))
            ttk.Label(bar,text="Время поиска").pack(side="left",padx=(0,7))
            ttk.Combobox(bar,textvariable=self.budget,values=tuple(BUDGETS),state="readonly",width=17).pack(side="left")
            self.finish_button=ttk.Button(bar,text="Сохранить найденное",command=self.finish_search,state="disabled")
            self.finish_button.pack(side="right")
        self.bar=ttk.Progressbar(form,mode="indeterminate")
        self.bar.grid(row=11,column=0,columnspan=3,sticky="ew",pady=(7,2))
        ttk.Label(form,textvariable=self.status,wraplength=670).grid(row=12,column=0,columnspan=3,sticky="w")
        paint=ttk.Checkbutton(form,text="Роспись главного поля",variable=self.painting)
        paint.grid(row=4,column=2,sticky="w")
        self.settings=[o for o in form.winfo_children() if int(o.grid_info().get("row",-1)) in (2,3,4,7,8,9)]
        self.toggle_settings()
        self.root.protocol("WM_DELETE_WINDOW",self.close)

    def toggle_settings(self):
        for widget in self.settings:
            if self.advanced.get():widget.grid()
            else:widget.grid_remove()

    def finish_search(self):
        self.finish_event.set()
        self.finish_button.configure(state="disabled")
        self.status.set("Поиск завершится с лучшей найденной композицией")

    def cell(self,row,col,title):
        box=ttk.Frame(self.form)
        box.grid(row=row,column=col,sticky="ew",padx=(0,6) if col<2 else (0,0),pady=3)
        ttk.Label(box,text=title).pack(fill="x",pady=(0,1))
        return box

    def choose_folder(self):
        target=filedialog.askdirectory(mustexist=False,title="Папка для новых вариантов",
                                       initialdir=self.folder.get() if Path(self.folder.get()).is_dir() else str(Path.home()))
        if target:
            self.folder.set(target)

    def set_scan_value(self,value):
        self.scan.set(str(value) if value else "")
        self.scan_label.set(Path(value).name if value else "Встроенный")

    def set_scan(self):
        path=filedialog.askopenfilename(title="Наличник в плоскости XY, рельефом к +Z",
                                        filetypes=(("Полигональный скан","*.obj"),))
        if path:
            self.set_scan_value(path)

    def reveal(self):
        try:
            path=Path(self.folder.get()).expanduser().resolve()
            path.mkdir(parents=True,exist_ok=True)
            if os.name=="nt":
                os.startfile(str(path))
            else:
                subprocess.Popen(["open" if sys.platform=="darwin" else "xdg-open",str(path)])
        except OSError as exc:
            messagebox.showerror("Открытие папки",str(exc),parent=self.root)

    def load(self):
        path=filedialog.askopenfilename(title="Открыть рецепт мастерской",filetypes=(("Рецепт комнаты","*.json"),))
        if path:
            try:
                self.use_recipe(Path(path),restore=True)
                self.status.set("Рецепт открыт. Введите правку или пересоберите комнату с новыми настройками.")
            except (OSError,KeyError,TypeError,ValueError) as exc:
                messagebox.showerror("Ошибка рецепта",str(exc),parent=self.root)

    def use_recipe(self,path,restore):
        plan=read_recipe(path)
        self.project=path
        self.project_title.set("Открытый проект · "+plan["title"])
        self.edit_button.configure(state="normal")
        if restore:
            self.school.set(_key(SCHOOLS,plan["style"]))
            opts=plan.get("export",{})
            self.painting.set(opts.get("painting",True))
            self.quality.set(_key(QUALITIES,opts.get("detail",2)))
            for field,v in zip(self.size,opts.get("size_m",(9,6.7,4.9))):
                field.set(str(v))
            for field,key,default in zip(self.tuning,("relief","foliage_delta","gilding_delta"),(1,0,0)):
                field.set(str(opts.get(key,default)))
            self.set_scan_value(path.parent/opts["window_scan"] if opts.get("window_scan") else "")
            self.folder.set(str(path.parent))
            self.prompt.delete("1.0","end")
            self.seed.set("")
        return plan

    def arguments(self,edit):
        prompt=self.prompt.get("1.0","end").strip()
        size=tuple(_number(v.get()) for v in self.size)
        depth,foliage,gilt=(_number(v.get()) for v in self.tuning)
        if not (3.4<=min(size[:2])<=max(size[:2])<=18 and 2.7<=size[2]<=8):
            raise ValueError("Длина и ширина должны быть 3,4–18 м, высота 2,7–8 м.")
        if not (.35<=depth<=2 and -1<=foliage<=1 and -1<=gilt<=1 and 1<=self.drafts.get()<=4):
            raise ValueError("Глубина 0,35–2, поправки от −1 до 1, эскизов 1–4.")
        if not self.folder.get().strip():
            raise ValueError("Выберите папку для результатов.")
        if edit and not self.project:
            raise ValueError("Сначала откройте рецепт комнаты.")
        if edit and not prompt:
            raise ValueError("Введите правку в поле описания.")
        seed=int(self.seed.get()) if self.seed.get().strip() else (None if edit else secrets.randbelow(2147483647))
        style=SCHOOLS[self.school.get()]
        stamp=datetime.now().strftime("%Y%m%d-%H%M%S")
        path=Path(self.folder.get()).expanduser()/f"{style}-{stamp}-{uuid4().hex[:8]}.obj"
        return argparse.Namespace(out=path,recipe=self.project if edit else None,prompt=prompt,backend=ENGINES[self.engine.get()],
            drafts=self.drafts.get(),style=style,seed=seed,size=size,detail=QUALITIES[self.quality.get()],
            relief=depth,foliage=foliage,gilding=gilt,window_scan=Path(self.scan.get()) if self.scan.get() else None,
            no_scan=not bool(self.scan.get()),window_material=None,painting=self.painting.get(),
            ultra=True,dense=self.dense,avoid=self.project if not edit else None,
            budget=BUDGETS[self.budget.get()] if self.atelier else None,finish=self.finish_event.is_set)

    def start(self,edit):
        if self.busy:
            return
        try:
            args=self.arguments(edit)
        except (tk.TclError,ValueError,OSError) as exc:
            messagebox.showerror("Параметры комнаты",str(exc),parent=self.root)
            return
        self.busy=True
        self.finish_event.clear()
        if self.atelier:self.finish_button.configure(state="normal")
        for button in (self.open_button,self.new_button,self.edit_button):
            button.configure(state="disabled")
        self.bar.start(27)
        self.status.set("Подготовка проекта…")
        def background():
            try:
                result=export(args,lambda text:self.events.put(("status",text)))
                self.events.put(("done",result))
            except Exception as exc:
                self.events.put(("error",str(exc)))
        # Leaving the window does not interrupt a file that is already being saved.
        self.worker=threading.Thread(target=background,name="PalaceExport",daemon=False)
        self.worker.start()
        self.root.after(120,self.poll)

    def poll(self):
        while not self.events.empty():
            kind,payload=self.events.get()
            if kind=="status":
                self.status.set(payload)
                continue
            self.bar.stop()
            self.busy=False
            if self.atelier:self.finish_button.configure(state="disabled")
            for button in (self.open_button,self.new_button):
                button.configure(state="normal")
            self.edit_button.configure(state="normal" if self.project else "disabled")
            if kind=="error":
                self.status.set("Сборка остановлена. Предыдущий вариант сохранён.")
                messagebox.showerror("Сборка комнаты",payload,parent=self.root)
            else:
                path,counts=payload
                plan=self.use_recipe(path.with_suffix(".recipe.json"),restore=False)
                source={"native":"Qwen","architecture_qwen":"композиция Qwen","architecture_rules":"автономная композиция","procedural_random":"случайная композиция",
                        "procedural_prompt":"автономные правила"}.get(plan["source"],plan["source"])
                self.status.set(f"Сохранён {path.name} · полей {len(plan['layout'])} · {source} · {counts[1]:,} треугольников".replace(","," "))
        if self.busy:
            self.root.after(120,self.poll)

    def close(self):
        if self.busy and not messagebox.askokcancel("Мастерская завершает сборку",
                 "Расчёт продолжится в фоне и сохранит результат в выбранную папку. Закрыть окно?",parent=self.root):
            return
        self.root.destroy()


if __name__=="__main__":
    root=tk.Tk()
    Workshop(root)
    root.mainloop()
