"""Small standard-library desktop UI; long operations run off the UI thread."""
import json
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from .profiles import ROOT, FEATURES, inspect_game
from .package import GamePackage
from .runner import run_build, write_report
from .tankpack import validate_pack
from . import VERSION

def main():
    root=tk.Tk();root.title('坦无敌3000 / TankInvincible · '+VERSION);root.geometry('860x650')
    tabs=ttk.Notebook(root);tabs.pack(fill='both',expand=True)
    body=ttk.Frame(tabs,padding=18);tabs.add(body,text='APK 构建')
    editor=ttk.Frame(tabs);tabs.add(editor,text='坦克 / 模型 / 贴图')
    from .project_gui import mount
    mount(editor)
    ttk.Label(body,text='坦无敌3000 · 构建器',font=('',20,'bold')).pack(anchor='w')
    ttk.Label(body,text='导入原始 APK/APKS，检测后构建。未知版本会输出适配报告。').pack(anchor='w',pady=(8,16))
    variables={};events=queue.Queue();buttons=[]
    def row(label,key,save=False):
        frame=ttk.Frame(body);frame.pack(fill='x',pady=5)
        ttk.Label(frame,text=label,width=13).pack(side='left')
        var=tk.StringVar();variables[key]=var
        ttk.Entry(frame,textvariable=var).pack(side='left',fill='x',expand=True)
        def choose():
            path=filedialog.asksaveasfilename(defaultextension='.apk') if save else filedialog.askopenfilename()
            if path:var.set(path)
        ttk.Button(frame,text='选择',command=choose).pack(side='left',padx=(6,0))
    row('安装包','input');row('工具与签名配置','config');row('输出 APK','output',True)
    packs=[];pack_label=tk.StringVar(value='未选择新增坦克包')
    def select_packs():
        packs[:]=filedialog.askopenfilenames(filetypes=[('Tank Pack','*.tankpack')]);pack_label.set('已选择 '+str(len(packs))+' 辆新坦克')
    ttk.Button(body,text='选择新增坦克包（可多选）',command=select_packs).pack(anchor='w')
    ttk.Label(body,textvariable=pack_label).pack(anchor='w')
    variables['config'].set(str(ROOT/'builder.config.json'))
    variables['output'].set(str(ROOT/'dist/Attack-on-Tank-builder.apk'))
    selected={f:tk.BooleanVar(value=True) for f in FEATURES}
    feature_row=ttk.Frame(body);feature_row.pack(fill='x',pady=12)
    for f,label in zip(FEATURES,['无敌','无限弹药','对局换坦克']):
        ttk.Checkbutton(feature_row,text=label,variable=selected[f]).pack(side='left',padx=(0,25))
    actions=ttk.Frame(body);actions.pack(fill='x',pady=8)
    text=tk.Text(body,wrap='word',font=('',11),height=20);text.pack(fill='both',expand=True,pady=(12,0))
    def show(message):events.put(('log',str(message)))
    def background(function):
        values={k:v.get() for k,v in variables.items()};features=[f for f,v in selected.items() if v.get()]
        for button in buttons:button.config(state='disabled')
        def execute():
            try:function(values,features)
            except Exception as exc:show('失败：'+str(exc))
            finally:events.put(('done',None))
        threading.Thread(target=execute,daemon=True).start()
    def inspect(values,features):
        with GamePackage(values['input']) as game:report=inspect_game(game)
        write_report(report,Path(values['output']).parent,'inspection')
        show(json.dumps(report,ensure_ascii=False,indent=2))
    def build(values,features):run_build(values['input'],values['output'],values['config'],features,tankpacks=tuple(packs),log=show)
    for label,function in [('检测兼容性',inspect),('构建 APK',build)]:
        button=ttk.Button(actions,text=label,command=lambda f=function:background(f));button.pack(side='left',padx=(0,10));buttons.append(button)
    def pack():
        filename=filedialog.askopenfilename(filetypes=[('Tank Pack','*.tankpack'),('ZIP','*.zip')])
        if filename:background(lambda v,f:show(json.dumps(validate_pack(filename),ensure_ascii=False,indent=2)))
    button=ttk.Button(actions,text='校验 Tank Pack',command=pack);button.pack(side='left');buttons.append(button)
    def update():
        while not events.empty():
            kind,value=events.get()
            if kind=='done':
                for button in buttons:button.config(state='normal')
            else:text.insert('end',value+'\n');text.see('end')
        root.after(100,update)
    update();root.mainloop()
