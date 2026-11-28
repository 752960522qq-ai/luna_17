package com.luna17.aot;
import android.view.SurfaceView;
import android.view.View;
import android.view.ViewGroup;

/** Unity's Screen pixels cover its render surface, which may be letterboxed
 * or offset from the Android overlay. Both locations below use window pixels. */
final class GameViewport {
    private SurfaceView surface;
    private final int[] game=new int[2],overlay=new int[2];
    float x,y;
    private SurfaceView find(View v){
        if(v instanceof SurfaceView && v.isShown())return (SurfaceView)v;
        if(v instanceof ViewGroup){
            ViewGroup g=(ViewGroup)v;SurfaceView best=null;
            for(int i=0;i<g.getChildCount();i++){
                SurfaceView s=find(g.getChildAt(i));
                if(s!=null&&(best==null||(long)s.getWidth()*s.getHeight()>(long)best.getWidth()*best.getHeight()))best=s;
            }
            return best;
        }
        return null;
    }
    void map(View target,float nx,float ny){
        if(surface==null || !surface.isShown() || !surface.isAttachedToWindow())surface=find(target.getRootView());
        if(surface==null||surface.getWidth()<=0||surface.getHeight()<=0){x=nx*target.getWidth();y=ny*target.getHeight();return;}
        surface.getLocationInWindow(game);target.getLocationInWindow(overlay);
        x=game[0]-overlay[0]+nx*surface.getWidth();y=game[1]-overlay[1]+ny*surface.getHeight();
    }
}
