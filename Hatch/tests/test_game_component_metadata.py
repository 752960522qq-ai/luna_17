"""Check actual decoded 5.1.0 method records before relying on a Unity overload."""
import argparse, json, struct
from pathlib import Path

def verify(directory):
 strings=(directory/'section4.dat').read_bytes();methods=(directory/'section3.dat').read_bytes()
 assert len(methods)%30==0,'Unexpected protected metadata method layout'
 def named(name):
  index=strings.find(name.encode()+b'\0');assert index>=0,name
  return [{'declaring_type':struct.unpack_from('<H',methods,p+4)[0],
           'generic_container':struct.unpack_from('<h',methods,p+16)[0],
           'parameter_count':struct.unpack_from('<H',methods,p+28)[0],
           'token':hex(struct.unpack_from('<I',methods,p+18)[0])}
          for p in range(0,len(methods),30) if struct.unpack_from('<I',methods,p)[0]==index]
 public=named('GetComponentsInChildren');internal=named('GetComponentsInternal');single=named('GetComponentInChildren')
 # GameObject's actual declaring type index in the protected 5.1.0 metadata.
 go=0x17ca
 assert not any(m['declaring_type']==go and m['generic_container']==-1 and m['parameter_count']==2 for m in public)
 assert any(m['declaring_type']==go and m['generic_container']==-1 and m['parameter_count']==6 for m in internal)
 assert any(m['declaring_type']==go and m['generic_container']==-1 and m['parameter_count']==2 for m in single)
 return {'public_child_array':public,'internal_components':internal,'single_child':single,'checks_passed':3}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--decoded',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
 result=verify(a.decoded);a.report.write_text(json.dumps(result,indent=2)+'\n');print('3 actual game metadata checks passed')
