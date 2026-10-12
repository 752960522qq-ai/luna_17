import subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HARNESS='''package com.luna17.aot;public class GestureTest {
static void check(boolean c){if(!c)throw new AssertionError();}
static void zero(float[] v){check(v[0]==0&&v[1]==0&&v[2]==0);}
public static void main(String[] args){
check(ArtilleryGesture.canCapture(.5f,.5f));check(!ArtilleryGesture.canCapture(.9f,.5f));check(!ArtilleryGesture.canCapture(.1f,.8f));check(!ArtilleryGesture.canCapture(.1f,.2f));ArtilleryGesture g=new ArtilleryGesture();zero(g.sample(new int[]{4},new float[]{100},new float[]{100},false,1000,500));
float[] a=g.sample(new int[]{4},new float[]{200},new float[]{150},true,1000,500);check(Math.abs(a[0]-.1)<.0001&&Math.abs(a[1]-.1)<.0001&&a[2]==0);
zero(g.sample(new int[]{4,9},new float[]{200,300},new float[]{150,150},false,1000,500));
a=g.sample(new int[]{4,9},new float[]{180,340},new float[]{200,200},true,1000,500);check(a[2]<0&&Math.abs(a[0]-.01)<.0001&&Math.abs(a[1]-.1)<.0001);
zero(g.sample(new int[]{9},new float[]{340},new float[]{200},false,1000,500));a=g.sample(new int[]{9},new float[]{350},new float[]{200},true,1000,500);check(Math.abs(a[0]-.01)<.0001);
g.reset();zero(g.sample(new int[]{2},new float[]{700},new float[]{100},true,1000,500));
System.out.println("Artillery gestures: one/two-finger pan, pinch, pointer-up identity, cancel/reset without jumps");}}
'''
class Gesture(unittest.TestCase):
 def test_pointer_transitions_and_pinch(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);src=p/'GestureTest.java';src.write_text(HARNESS)
   subprocess.run(['java','com.sun.tools.javac.Main','--release','8','-d',d,str(src),str(ROOT/'mods/tankinvincible/src/com/luna17/aot/ArtilleryGesture.java')],check=True)
   subprocess.run(['java','-cp',d,'com.luna17.aot.GestureTest'],check=True)
