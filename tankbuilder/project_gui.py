"""Desktop project editor; model conversion stays local."""
import json,shutil
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from pathlib import Path
from .project import (create_project,read_documents,save_documents,validate_project,
    import_model,replace_texture,pack_project,NATIONS)

def mount(parent):
    top=ttk.Frame(parent,padding=12);top.pack(fill='both',expand=True)
    project=tk.StringVar();state=tk.StringVar(value='打开项目，或从 T54 模板创建新项目。模板参数可编辑。')
    row=ttk.Frame(top);row.pack(fill='x');ttk.Entry(row,textvariable=project).pack(side='left',fill='x',expand=True)
    text=tk.Text(top,height=18,wrap='none');text.pack(fill='both',expand=True,pady=12)
    def load():
        docs=read_documents(project.get());text.delete('1.0','end');text.insert('1.0',json.dumps(docs,ensure_ascii=False,indent=2));state.set('编辑名称、国家、数值与绑定后保存；贴图按材质名称替换。')
    def action(fn):
        try:fn()
        except Exception as e:messagebox.showerror('未完成',str(e))
    def open_project():
        path=filedialog.askdirectory()
        if path:project.set(path);load()
    def new_project():
        from tkinter.simpledialog import askstring
        ident=askstring('新坦克','坦克 ID（字母、数字、下划线）')
        if not ident:return
        parent=filedialog.askdirectory(title='选择新项目的父目录')
        if not parent:return
        output=Path(parent)/ident;result=create_project(output,ident=ident);project.set(str(output));load();state.set(json.dumps(result,ensure_ascii=False))
    ttk.Button(row,text='打开项目',command=lambda:action(open_project)).pack(side='left',padx=6)
    ttk.Button(row,text='新建坦克',command=lambda:action(new_project)).pack(side='left')
    def save():
        docs=json.loads(text.get('1.0','end'));save_documents(project.get(),docs)
        result=validate_project(project.get());state.set('检查通过' if result['valid'] else '\n'.join(result['errors']))
        return result
    def model():
        file=filedialog.askopenfilename(filetypes=[('GLB 模型','*.glb')])
        if file:result=import_model(project.get(),file);load();state.set(json.dumps(result,ensure_ascii=False))
    def thumbnail():
        file=filedialog.askopenfilename(filetypes=[('PNG 缩略图','*.png')])
        if file:
            from PIL import Image
            Image.open(file).verify();shutil.copyfile(file,Path(project.get())/'thumbnail.png');state.set('缩略图已导入')
    def texture(slot='baseColor'):
        from tkinter.simpledialog import askstring
        material=askstring('材质','输入模型内的材质名称')
        if not material:return
        file=filedialog.askopenfilename(filetypes=[('贴图','*.png *.jpg *.jpeg *.webp')])
        if file:state.set(json.dumps(replace_texture(project.get(),material,file,slot),ensure_ascii=False))
    def export():
        r=save()
        if not r['valid']:raise ValueError('项目检查未通过')
        file=filedialog.asksaveasfilename(defaultextension='.tankpack')
        if file:state.set(json.dumps(pack_project(project.get(),file),ensure_ascii=False))
    buttons=ttk.Frame(top);buttons.pack(fill='x')
    for label,fn in [('保存并检查',save),('导入模型与绑定',model),('缩略图',thumbnail),('颜色贴图',texture),('法线贴图',lambda:texture('normal')),('导出 Tank Pack',export)]:ttk.Button(buttons,text=label,command=lambda f=fn:action(f)).pack(side='left',padx=(0,8))
    ttk.Label(top,textvariable=state,wraplength=780).pack(anchor='w',pady=10)
    return project
