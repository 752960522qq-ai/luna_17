"""Single source for shell order, charge units and package validation."""
import copy,math
SHELLS=('AP','HE','APCR','WP','HEAT')
def charge_grams(shell):
 if not isinstance(shell,dict):raise ValueError('炮弹参数须为对象')
 values=[]
 for key,mult in (('explosiveMassGrams',1),('explosiveMassKg',1000)):
  if key in shell:
   v=shell[key]
   if type(v) not in (int,float) or not math.isfinite(v) or not 0<=v*mult<=100000:raise ValueError('装药量须为0–100000克')
   values.append(v*mult)
 if len(values)==2 and not math.isclose(*values,rel_tol=1e-6,abs_tol=1e-6):raise ValueError('克和千克装药量不一致')
 return values[0] if values else None
def filling_table(weapon,require_active=False):
 result={};shells=weapon.get('shells',{})
 for kind in SHELLS:
  value=charge_grams(shells.get(kind,{}))
  if value is not None:result[kind]=value
  elif require_active and weapon.get('ammo',{}).get(kind,0)>0:raise ValueError(kind+'缺少独立装药量；无装药请显式填0')
 return result
def filling_vector(weapon):
 table=filling_table(weapon,True)
 return [table.get(k,0) for k in SHELLS],sum(1<<i for i,k in enumerate(SHELLS) if k in table)
def apply_filling_overrides(weapon,overrides):
 result=copy.deepcopy(weapon)
 for kind,value in overrides.items():
  if kind not in SHELLS:raise ValueError('未知弹种')
  if value is None:continue
  charge_grams({'explosiveMassGrams':value})
  shell=result.setdefault('shells',{}).setdefault(kind,{})
  shell.pop('explosiveMassKg',None);shell['explosiveMassGrams']=value
 filling_table(result,True);return result
