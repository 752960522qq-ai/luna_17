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
    private float[] data=new float[28];
    private View pad;
    private TextView hint;
    private final ArtilleryGesture gesture=new ArtilleryGesture();
    private boolean captured,moved;
    private float downX,downY;
    private TextView broadcast;
    private int contactSequence;
    private long contactUntil;
    ExperienceHud(Activity activity){this.activity=activity;}
    private int dp(float n){return Math.round(n*activity.getResources().getDisplayMetrics().density);}
    void attach(){
        stopped=false;root=new FrameLayout(activity);
        View drawing=new View(activity){
            @Override protected void onDraw(Canvas canvas){
                if(stopped)return;
                float[] snapshot=NativeBridge.experienceSnapshot();if(snapshot!=null && snapshot.length==28)data=snapshot;
                int[] contact=NativeBridge.crewContactSnapshot();
                long now=android.os.SystemClock.uptimeMillis();
                if(contact!=null&&contact.length==5&&contact[4]==1&&contact[0]!=contactSequence){contactSequence=contact[0];contactUntil=now+4000;broadcast.setText(String.format(Locale.ROOT,"已锁定%s · %d点钟 · %d m",contact[1]==2?"敌机":"敌方坦克",contact[2],contact[3]));}
                broadcast.setVisibility(data[0]==1&&now<contactUntil?View.VISIBLE:View.GONE);
                boolean active=data[0]==1,spg=active&&data[8]==1;
                pad.setVisibility(spg&&data[9]==2?View.VISIBLE:View.GONE);
                hint.setVisibility(spg?View.VISIBLE:View.GONE);
                if(active){
                    float w=getWidth(),h=getHeight();paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(dp(2));
                    if(data[1]==1){
                        paint.setColor(Color.rgb(80,255,135));float x=data[2]*w,y=data[3]*h;
                        canvas.drawCircle(x,y,dp(7),paint);canvas.drawLine(x-dp(12),y,x+dp(12),y,paint);canvas.drawLine(x,y-dp(12),x,y+dp(12),paint);
                        if(spg&&data[9]==2){float rx=Math.max(dp(3),data[13]*w),ry=Math.max(dp(3),data[14]*h);canvas.drawOval(x-rx,y-ry,x+rx,y+ry,paint);}
                    }
                    if(spg&&data[9]==2&&data[24]==1){paint.setColor(data[25]==1?Color.CYAN:Color.rgb(255,160,40));canvas.drawCircle(data[22]*w,data[23]*h,dp(11),paint);}
                    if(data[4]==1){
                        paint.setColor(Color.rgb(255,190,60));float x=data[5]*w,y=data[6]*h;
                        canvas.drawCircle(x,y,dp(10),paint);canvas.drawLine(x-dp(5),y,x+dp(5),y,paint);canvas.drawLine(x,y-dp(5),x,y+dp(5),paint);
                    }
                    if(spg&&data[9]==2 && data[19]>0 && data[20]>0){
                        paint.setColor(Color.argb(110,100,180,255));float x=data[16]*w,y=data[17]*h;
                        canvas.drawOval(x-data[19]*w,y-data[20]*h,x+data[19]*w,y+data[20]*h,paint);
                    }
                    if(spg)hint.setText(data[21]==0?"弹道数据不可用":data[1]==0?"当前弹道在 3000 m 预览范围内未命中\n点击选定目标 / 拖动平移 / 双指缩放":String.format(Locale.ROOT,"落点 %.0f m · %.1f s\n散布半径 %.1f m · 平地射程 ≤%.0f m\n俯角 %.0f° · 点击选定目标 / 拖动平移 / 双指缩放",data[10],data[11],data[12],data[15],data[18]));
                }
                postInvalidateDelayed(50);
            }
        };
        root.addView(drawing,new FrameLayout.LayoutParams(-1,-1));
        hint=new TextView(activity);hint.setTextColor(Color.WHITE);hint.setTextSize(12);hint.setShadowLayer(3,0,0,Color.BLACK);hint.setVisibility(View.GONE);
        FrameLayout.LayoutParams label=new FrameLayout.LayoutParams(dp(285),-2,Gravity.TOP|Gravity.CENTER_HORIZONTAL);label.topMargin=dp(12);root.addView(hint,label);
        pad=new View(activity);pad.setVisibility(View.GONE);
        root.addView(pad,new FrameLayout.LayoutParams(-1,-1));
        pad.setOnTouchListener((view,event)->{
            int action=event.getActionMasked();
            if(action==MotionEvent.ACTION_DOWN){
                float x=event.getX()/view.getWidth(),y=event.getY()/view.getHeight();
                // Preserve Unity's joystick, top toolbar and right fire/scope buttons.
                captured=ArtilleryGesture.canCapture(x,y);moved=false;downX=event.getX();downY=event.getY();
                gesture.reset();if(!captured)return false;
            }
            if(!captured)return false;
            if(event.getPointerCount()>1||Math.hypot(event.getX()-downX,event.getY()-downY)>dp(8))moved=true;
            if(action==MotionEvent.ACTION_UP&&!moved)NativeBridge.experienceTarget(event.getX()/view.getWidth(),event.getY()/view.getHeight());
            int removed=action==MotionEvent.ACTION_POINTER_UP?event.getActionIndex():-1;
            int count=event.getPointerCount()-(removed>=0?1:0);
            int[] ids=new int[count];float[] xs=new float[count],ys=new float[count];
            for(int i=0,j=0;i<event.getPointerCount();i++)if(i!=removed){ids[j]=event.getPointerId(i);xs[j]=event.getX(i);ys[j++]=event.getY(i);}
            float[] command=gesture.sample(ids,xs,ys,action==MotionEvent.ACTION_MOVE,view.getWidth(),view.getHeight());
            if(action==MotionEvent.ACTION_MOVE)NativeBridge.experienceInput(0,command[0],command[1],command[2],0);
            if(action==MotionEvent.ACTION_UP||action==MotionEvent.ACTION_CANCEL){gesture.reset();captured=false;}
            return true;
        });
        broadcast=new TextView(activity);broadcast.setTextColor(Color.WHITE);broadcast.setTextSize(16);broadcast.setShadowLayer(3,0,0,Color.BLACK);broadcast.setVisibility(View.GONE);
        FrameLayout.LayoutParams notice=new FrameLayout.LayoutParams(-2,-2,Gravity.TOP|Gravity.CENTER_HORIZONTAL);notice.topMargin=dp(42);root.addView(broadcast,notice);
        activity.addContentView(root,new android.view.ViewGroup.LayoutParams(-1,-1));
    }
    void detach(){stopped=true;if(root!=null && root.getParent() instanceof android.view.ViewGroup)((android.view.ViewGroup)root.getParent()).removeView(root);root=null;}
}
