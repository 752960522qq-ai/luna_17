package com.luna17.aot;

import android.app.Activity;
import android.graphics.*;
import android.view.*;
import android.widget.*;
import java.util.Locale;

/** Transparent output layer plus a bounded artillery touch pad. */
final class ExperienceHud {
    private final Activity activity;
    private FrameLayout root;
    private boolean stopped;
    private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
    private float[] data=new float[24];
    private Button mode;
    private View pad;
    private TextView hint;
    private float lastX,lastY,lastDistance;
    private int pointers;
    ExperienceHud(Activity activity){this.activity=activity;}
    private int dp(float n){return Math.round(n*activity.getResources().getDisplayMetrics().density);}
    void attach(){
        stopped=false;root=new FrameLayout(activity);
        View drawing=new View(activity){
            @Override protected void onDraw(Canvas canvas){
                if(stopped)return;
                float[] snapshot=NativeBridge.experienceSnapshot();if(snapshot!=null && snapshot.length==24)data=snapshot;
                boolean active=data[0]==1,spg=active&&data[8]==1;
                mode.setVisibility(spg?View.VISIBLE:View.GONE);
                pad.setVisibility(spg&&data[9]==2?View.VISIBLE:View.GONE);
                hint.setVisibility(spg?View.VISIBLE:View.GONE);
                mode.setText(data[9]==1?"一级镜 2.5×":data[9]==2?"二级镜 俯瞰":"火炮镜");
                if(active){
                    float w=getWidth(),h=getHeight();paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(dp(2));
                    if(data[1]==1){
                        paint.setColor(Color.rgb(80,255,135));float x=data[2]*w,y=data[3]*h;
                        canvas.drawCircle(x,y,dp(7),paint);canvas.drawLine(x-dp(12),y,x+dp(12),y,paint);canvas.drawLine(x,y-dp(12),x,y+dp(12),paint);
                        if(spg&&data[9]==2){float rx=Math.max(dp(3),data[13]*w),ry=Math.max(dp(3),data[14]*h);canvas.drawOval(x-rx,y-ry,x+rx,y+ry,paint);}
                    }
                    if(data[4]==1){
                        paint.setColor(Color.rgb(255,190,60));float x=data[5]*w,y=data[6]*h;
                        canvas.drawCircle(x,y,dp(10),paint);canvas.drawLine(x-dp(5),y,x+dp(5),y,paint);canvas.drawLine(x,y-dp(5),x,y+dp(5),paint);
                    }
                    if(spg&&data[9]==2 && data[19]>0 && data[20]>0){
                        paint.setColor(Color.argb(110,100,180,255));float x=data[16]*w,y=data[17]*h;
                        canvas.drawOval(x-data[19]*w,y-data[20]*h,x+data[19]*w,y+data[20]*h,paint);
                    }
                    if(spg)hint.setText(data[21]==0?"弹道数据不可用":data[1]==0?"当前弹道在 3000 m 预览范围内未命中\n单指平移 / 双指缩放 / 双指上下调俯角":String.format(Locale.ROOT,"落点 %.0f m · %.1f s\n散布半径 %.1f m · 平地射程 ≤%.0f m\n俯角 %.0f° · 单指平移 / 双指缩放 / 双指上下调俯角",data[10],data[11],data[12],data[15],data[18]));
                }
                postInvalidateDelayed(50);
            }
        };
        root.addView(drawing,new FrameLayout.LayoutParams(-1,-1));
        mode=new Button(activity);mode.setText("火炮镜");mode.setVisibility(View.GONE);
        mode.setOnClickListener(v->NativeBridge.experienceInput(1,0,0,0,0));
        FrameLayout.LayoutParams button=new FrameLayout.LayoutParams(dp(135),dp(48),Gravity.TOP|Gravity.RIGHT);button.topMargin=dp(54);button.rightMargin=dp(12);root.addView(mode,button);
        hint=new TextView(activity);hint.setTextColor(Color.WHITE);hint.setTextSize(12);hint.setShadowLayer(3,0,0,Color.BLACK);hint.setVisibility(View.GONE);
        FrameLayout.LayoutParams label=new FrameLayout.LayoutParams(dp(285),-2,Gravity.TOP|Gravity.CENTER_HORIZONTAL);label.topMargin=dp(12);root.addView(hint,label);
        pad=new View(activity);pad.setBackgroundColor(Color.argb(42,70,110,150));pad.setVisibility(View.GONE);
        FrameLayout.LayoutParams touch=new FrameLayout.LayoutParams(dp(170),dp(145),Gravity.BOTTOM|Gravity.RIGHT);touch.rightMargin=dp(14);touch.bottomMargin=dp(105);root.addView(pad,touch);
        pad.setOnTouchListener((view,event)->{
            int count=event.getPointerCount();float x=event.getX(),y=event.getY(),distance=0;
            if(count>=2){x=(x+event.getX(1))*.5f;y=(y+event.getY(1))*.5f;distance=(float)Math.hypot(event.getX()-event.getX(1),event.getY()-event.getY(1));}
            if(event.getActionMasked()==MotionEvent.ACTION_MOVE && count==pointers){
                if(count>=2){float zoom=distance>1&&lastDistance>1?(float)Math.log(lastDistance/distance):0;NativeBridge.experienceInput(0,0,0,zoom,(y-lastY)/view.getHeight()*45);}
                else NativeBridge.experienceInput(0,(x-lastX)/view.getWidth(),(y-lastY)/view.getHeight(),0,0);
            }
            lastX=x;lastY=y;lastDistance=distance;pointers=count;
            if(event.getActionMasked()==MotionEvent.ACTION_UP||event.getActionMasked()==MotionEvent.ACTION_CANCEL)pointers=0;
            return true;
        });
        activity.addContentView(root,new android.view.ViewGroup.LayoutParams(-1,-1));
    }
    void detach(){stopped=true;if(root!=null && root.getParent() instanceof android.view.ViewGroup)((android.view.ViewGroup)root.getParent()).removeView(root);root=null;}
}
