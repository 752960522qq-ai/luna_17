"""Run the actual dependency resolver on the JVM, including failure cases."""
import subprocess
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HARNESS='''package com.hatch.loader;
import java.util.*;import java.io.*;
public class DependencyCheck {
static DependencyOrder.Node n(String id,String version,String... deps){Map<String,String> r=new HashMap<>();for(int i=0;i<deps.length;i+=2)r.put(deps[i],deps[i+1]);return new DependencyOrder.Node(id,version,r);}
static void bad(DependencyOrder.Node... nodes)throws Exception{try{DependencyOrder.resolve(Arrays.asList(nodes));throw new AssertionError();}catch(IOException expected){}}
public static void main(String[] args)throws Exception {
List<DependencyOrder.Node> nodes=Arrays.asList(n("tank","1.0","feature","0.1"),n("feature","0.1","core","1.0"),n("core","1.0"));
if(!DependencyOrder.resolve(nodes).equals(Arrays.asList("core","feature","tank")))throw new AssertionError();
bad(n("a","1.0","missing","1.0"));bad(n("a","1.0","b","2.0"),n("b","1.0"));
bad(n("a","1.0","b","1.0"),n("b","1.0","a","1.0"));bad(n("a","1.0","a","1.0"));bad(n("a","1.0"),n("a","1.0"));
System.out.println("Dependency ordering and five rejection cases passed");}}
'''
class Dependencies(unittest.TestCase):
    def test_production_resolver(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);file=path/'DependencyCheck.java';file.write_text(HARNESS)
            subprocess.run(['java','com.sun.tools.javac.Main','--release','8','-d',temp,str(ROOT/'loader/src/com/hatch/loader/DependencyOrder.java'),str(file)],check=True)
            subprocess.run(['java','-cp',temp,'com.hatch.loader.DependencyCheck'],check=True)
if __name__=='__main__':unittest.main()
