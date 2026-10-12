import subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STUBS={
'org/json/JSONObject.java':'''package org.json;import java.util.*;public class JSONObject {Map<String,Object> m=new LinkedHashMap<>();public JSONObject put(String k,Object v){m.put(k,v);return this;}public int length(){return m.size();}public Iterator<String> keys(){return m.keySet().iterator();}public JSONObject getJSONObject(String k){return (JSONObject)m.get(k);}public boolean has(String k){return m.containsKey(k);}public boolean isNull(String k){return m.get(k)==null;}public double getDouble(String k){return ((Number)m.get(k)).doubleValue();}}''',
'com/luna17/aot/NativeBridge.java':'''package com.luna17.aot;public class NativeBridge {static int writes,mask;static float[] values;static boolean configureAmmunition(String id,float[] grams,int m){writes++;mask=m;values=grams;return true;}}''',
'com/luna17/aot/AmmoTest.java':'''package com.luna17.aot;import org.json.*;public class AmmoTest {static void check(boolean c){if(!c)throw new AssertionError();}public static void main(String[] args)throws Exception{check(AmmunitionSettings.apply(null).isEmpty());JSONObject table=new JSONObject().put("SU_152",new JSONObject().put("HE",5860).put("AP",0).put("WP",null));check(AmmunitionSettings.apply(table).isEmpty());check(NativeBridge.mask==3&&NativeBridge.values[1]==5860&&NativeBridge.values[0]==0);NativeBridge.writes=0;table.put("bad",new JSONObject().put("HE",Double.NaN));check(!AmmunitionSettings.apply(table).isEmpty()&&NativeBridge.writes==0);table.put("bad",new JSONObject().put("HE",100001));check(!AmmunitionSettings.apply(table).isEmpty()&&NativeBridge.writes==0);table.put("bad",new JSONObject().put("wrong",1));check(!AmmunitionSettings.apply(table).isEmpty()&&NativeBridge.writes==0);System.out.println("Charge table validates all vehicles before writes; zero, null, finite and shell identity checks passed");}}'''
}
class AmmunitionSettings(unittest.TestCase):
 def test_actual_parser_atomic_validation(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);files=[]
   for name,text in STUBS.items():
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text);files.append(str(p))
   files.append(str(ROOT/'mods/tankinvincible/src/com/luna17/aot/AmmunitionSettings.java'))
   subprocess.run(['java','com.sun.tools.javac.Main','--release','8','-d',d,*files],check=True)
   subprocess.run(['java','-cp',d,'com.luna17.aot.AmmoTest'],check=True)
if __name__=='__main__':unittest.main()
