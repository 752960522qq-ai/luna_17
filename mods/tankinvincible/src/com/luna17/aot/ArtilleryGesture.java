package com.luna17.aot;
/** Pointer identities and transition baselines, independent of Android dispatch. */
final class ArtilleryGesture {
    static boolean canCapture(float x,float y){return x>.03f&&x<.80f&&y>.18f&&y<.96f&&!(x<.29f&&y<.40f)&&!(x<.23f&&y>.64f);}
    private int first=-1,second=-1;
    private float x,y,distance;
    void reset(){first=second=-1;distance=0;}
    float[] sample(int[] ids,float[] xs,float[] ys,boolean moving,float width,float height){
        if(ids.length==0){reset();return new float[3];}
        int a=ids[0],b=ids.length>1?ids[1]:-1;
        float cx=xs[0],cy=ys[0],d=0;
        if(b!=-1){cx=(cx+xs[1])*.5f;cy=(cy+ys[1])*.5f;d=(float)Math.hypot(xs[0]-xs[1],ys[0]-ys[1]);}
        float[] output=new float[3];
        if(moving&&a==first&&b==second&&width>0&&height>0){
            output[0]=(cx-x)/width;output[1]=(cy-y)/height;
            if(b!=-1&&d>1&&distance>1)output[2]=(float)Math.log(distance/d);
        }
        first=a;second=b;x=cx;y=cy;distance=d;return output;
    }
}
