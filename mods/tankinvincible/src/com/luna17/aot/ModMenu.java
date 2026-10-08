package com.luna17.aot;

import com.hatch.loader.HatchLoader;

import android.app.Activity;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Handler;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.CompoundButton;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;
import java.util.Arrays;

final class ModMenu {
    private final Activity activity;
    private final Handler handler = new Handler(android.os.Looper.getMainLooper());
    private FrameLayout overlay;
    private Button bubble, swap, spawnEnemy;
    private ScrollView panel;
    private TextView status, result, enemyResult;
    private CheckBox god, ammo;
    private Spinner nation, tank, enemyNation, enemyTank;
    private String[] currentTanks = new String[0];
    private String[] currentEnemies = new String[0];
    private int shownEnemyNation = -1;
    private boolean waitingEnemy;
    private int shownNation = -1, currentState;
    private boolean changing, waiting, stopped;
    private final int white = Color.rgb(237, 242, 249);
    private final int muted = Color.rgb(165, 182, 202);
    private final int accent = Color.rgb(255, 122, 90);
    private final Runnable poll = new Runnable() {
        @Override public void run() {
            if (stopped) return;
            refresh();
            handler.postDelayed(this, 800);
        }
    };

    ModMenu(Activity activity) { this.activity = activity; }
    private int dp(float value) { return (int)(value * activity.getResources().getDisplayMetrics().density + .5f); }
    private GradientDrawable background(int color, int radius) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(color); d.setCornerRadius(dp(radius));
        d.setStroke(dp(1), Color.rgb(64, 83, 107));
        return d;
    }
    private TextView label(String text, int size, int color) {
        TextView v = new TextView(activity);
        v.setText(text); v.setTextSize(size); v.setTextColor(color);
        v.setPadding(dp(4), dp(7), dp(4), dp(7));
        return v;
    }
    private Button button(String text) {
        Button b = new Button(activity); b.setText(text); b.setTextColor(white);
        b.setTextSize(13); b.setBackground(background(Color.rgb(41, 59, 82), 9));
        return b;
    }

    void attach() {
        overlay = new FrameLayout(activity);
        overlay.setClipChildren(false);
        bubble = button("坦无敌\n3000");
        bubble.setTextSize(11);
        bubble.setPadding(0,0,0,0);
        bubble.setMinWidth(0); bubble.setMinHeight(0);
        bubble.setMaxLines(2);
        bubble.setTextColor(Color.WHITE);
        bubble.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        bubble.setBackground(background(Color.rgb(187, 74, 46), 24));
        FrameLayout.LayoutParams bp = new FrameLayout.LayoutParams(dp(52), dp(48), Gravity.LEFT | Gravity.TOP);
        bp.leftMargin = dp(18); bp.topMargin = dp(22);
        overlay.addView(bubble, bp);
        buildPanel();
        bubble.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) {
                panel.setVisibility(panel.getVisibility() == View.VISIBLE ? View.GONE : View.VISIBLE);
                if (panel.getVisibility() == View.VISIBLE) { positionPanel(); refresh(); }
            }
        });
        bubble.setOnTouchListener(new View.OnTouchListener() {
            float startX, startY; int originalX, originalY; boolean moved;
            @Override public boolean onTouch(View v, MotionEvent event) {
                FrameLayout.LayoutParams lp = (FrameLayout.LayoutParams)bubble.getLayoutParams();
                if (event.getAction() == MotionEvent.ACTION_DOWN) {
                    startX = event.getRawX(); startY = event.getRawY();
                    originalX = lp.leftMargin; originalY = lp.topMargin; moved = false; return true;
                }
                if (event.getAction() == MotionEvent.ACTION_MOVE) {
                    float dx = event.getRawX() - startX, dy = event.getRawY() - startY;
                    moved |= Math.abs(dx) + Math.abs(dy) > dp(8);
                    if (moved) {
                        lp.leftMargin = Math.max(0, Math.min(Math.max(0, overlay.getWidth()-dp(52)), originalX+(int)dx));
                        lp.topMargin = Math.max(0, Math.min(Math.max(0, overlay.getHeight()-dp(48)), originalY+(int)dy));
                        bubble.setLayoutParams(lp); positionPanel();
                    }
                    return true;
                }
                if (event.getAction() == MotionEvent.ACTION_UP) { if (!moved) bubble.performClick(); return true; }
                return event.getAction() == MotionEvent.ACTION_CANCEL;
            }
        });
        activity.addContentView(overlay, new ViewGroup.LayoutParams(-1,-1));
        overlay.post(new Runnable() { @Override public void run() { positionPanel(); }});
        handler.post(poll);
        toast("修改菜单已载入，点击左上角坦无敌3000");
    }

    private void buildPanel() {
        LinearLayout body = new LinearLayout(activity);
        body.setOrientation(LinearLayout.VERTICAL); body.setPadding(dp(14),dp(10),dp(14),dp(12));
        body.setBackground(background(Color.argb(248, 19, 30, 46), 13));
        body.setClickable(true);
        TextView title = label("坦无敌3000 1.0", 17, white);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD); body.addView(title);
        body.addView(label("必备前置模组", 12, muted));
        body.addView(label(FeatureConfig.BUILD_LABEL, 11, muted));
        status = label("等待游戏模块…", 12, accent); body.addView(status);
        Button importTank=button("舱盖 0.3 · 管理 / 导入模组");body.addView(importTank);
        importTank.setOnClickListener(v -> HatchLoader.show(activity));
        god = feature("无敌", 0); body.addView(god);
        ammo = feature("无限弹药", 1); body.addView(ammo);
        body.addView(label("对局换坦克", 14, white));
        nation = new Spinner(activity);
        String[] countries = {"苏联", "德国", "美国", "日本", "英国", "意大利"};
        nation.setAdapter(adapter(countries)); body.addView(nation, new LinearLayout.LayoutParams(-1,dp(42)));
        tank = new Spinner(activity); tank.setAdapter(adapter(new String[]{"进入单人对局后读取车型"}));
        body.addView(tank, new LinearLayout.LayoutParams(-1,dp(42)));
        nation.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override public void onItemSelected(AdapterView<?> a,View v,int p,long id) { refreshTanks(); }
            @Override public void onNothingSelected(AdapterView<?> a) {}
        });
        swap = button("替换当前坦克");
        LinearLayout.LayoutParams sp = new LinearLayout.LayoutParams(-1,dp(43)); sp.topMargin=dp(7); body.addView(swap,sp);
        swap.setEnabled(false);
        swap.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) {
                int n = nation.getSelectedItemPosition(), i = tank.getSelectedItemPosition();
                if (NativeBridge.loaded && NativeBridge.switchTank(n,i)) {
                    waiting=true; result.setText("正在对局中替换…"); swap.setEnabled(false);
                } else toast("请在单人对局中选择有效车型");
            }
        });
        result = label("新坦克保留当前位置和朝向。", 11, muted); body.addView(result);
        body.addView(label("添加敌人坦克", 14, white));
        enemyNation = new Spinner(activity); enemyNation.setAdapter(adapter(countries));
        body.addView(enemyNation, new LinearLayout.LayoutParams(-1,dp(42)));
        enemyTank = new Spinner(activity); enemyTank.setAdapter(adapter(new String[]{"进入单人对局后读取 AI 车型"}));
        body.addView(enemyTank, new LinearLayout.LayoutParams(-1,dp(42)));
        enemyNation.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override public void onItemSelected(AdapterView<?> a,View v,int p,long id) { refreshEnemies(); }
            @Override public void onNothingSelected(AdapterView<?> a) {}
        });
        spawnEnemy = button("在屏幕中心指向处添加敌人"); body.addView(spawnEnemy, new LinearLayout.LayoutParams(-1,dp(43)));
        spawnEnemy.setEnabled(false);
        enemyResult = label("先把屏幕中心对准地面，再选择原版 AI 坦克并添加。", 11, muted); body.addView(enemyResult);
        spawnEnemy.setOnClickListener(v -> {
            int n = enemyNation.getSelectedItemPosition(), i = enemyTank.getSelectedItemPosition();
            if (NativeBridge.loaded && NativeBridge.spawnEnemy(n,i)) {
                waitingEnemy = true; enemyResult.setText("正在添加敌人…");
                spawnEnemy.setEnabled(false); swap.setEnabled(false);
            } else toast("请在单人对局中选择有效 AI 车型，等待当前操作完成");
        });
        body.addView(label("单人模式可用；联机模式自动暂停。", 11, muted));
        Button close = button("收起菜单"); body.addView(close,new LinearLayout.LayoutParams(-1,dp(36)));
        close.setOnClickListener(new View.OnClickListener() { @Override public void onClick(View v) {panel.setVisibility(View.GONE);} });
        panel = new ScrollView(activity); panel.setFillViewport(false); panel.setClipToPadding(false);
        panel.addView(body); panel.setVisibility(View.GONE);
        overlay.addView(panel,new FrameLayout.LayoutParams(dp(318),dp(340),Gravity.LEFT|Gravity.TOP));
    }
    private CheckBox feature(String name,final int id) {
        final CheckBox c = new CheckBox(activity); c.setText(name); c.setTextSize(15); c.setTextColor(white);
        c.setEnabled(false); c.setPadding(dp(3),dp(4),0,dp(4));
        c.setOnCheckedChangeListener(new CompoundButton.OnCheckedChangeListener() {
            @Override public void onCheckedChanged(CompoundButton b,boolean enabled) {
                if (changing) return;
                if (!NativeBridge.loaded || !NativeBridge.toggle(id,enabled)) {
                    changing=true; c.setChecked(!enabled); changing=false;
                    toast("模块未就绪，或当前为联机模式");
                }
            }
        });
        return c;
    }
    private ArrayAdapter<String> adapter(String[] items) {
        return new ArrayAdapter<String>(activity, android.R.layout.simple_spinner_item, items) {
            @Override public View getView(int p,View old,ViewGroup parent) {
                TextView v=(TextView)super.getView(p,old,parent); v.setTextColor(white); v.setTextSize(13); return v;
            }
            @Override public View getDropDownView(int p,View old,ViewGroup parent) {
                TextView v=(TextView)super.getDropDownView(p,old,parent); v.setTextColor(white);
                v.setBackgroundColor(Color.rgb(34,48,67)); v.setPadding(dp(9),dp(13),dp(9),dp(13)); return v;
            }
        };
    }
    private void positionPanel() {
        if (overlay.getWidth() == 0 || overlay.getHeight() == 0) return;
        FrameLayout.LayoutParams b=(FrameLayout.LayoutParams)bubble.getLayoutParams();
        FrameLayout.LayoutParams p=(FrameLayout.LayoutParams)panel.getLayoutParams();
        p.width=Math.min(dp(318),overlay.getWidth()-dp(16));
        p.height=Math.min(dp(440),overlay.getHeight()-dp(16));
        p.leftMargin=Math.max(dp(8),Math.min(b.leftMargin+dp(58),overlay.getWidth()-p.width-dp(8)));
        p.topMargin=Math.max(dp(8),Math.min(b.topMargin,overlay.getHeight()-p.height-dp(8)));
        panel.setLayoutParams(p);
    }
    private void refreshTanks() {
        if (tank==null || nation==null || !NativeBridge.loaded) return;
        int n=nation.getSelectedItemPosition();
        String[] next=NativeBridge.tanks(n);
        if (next == null) next=new String[0];
        if (n==shownNation && Arrays.equals(next,currentTanks)) return;
        shownNation=n; currentTanks=next;
        tank.setAdapter(adapter(next.length==0 ? new String[]{"进入单人对局后读取车型"} : next));
    }
    private void refresh() {
        try {
            currentState=NativeBridge.loaded ? NativeBridge.state() : -2;
            switch(currentState) {
                case 1: status.setText("正在接入游戏模块…"); break;
                case 2: status.setText("模块就绪 · 进入单人对局后生效"); break;
                case 3: status.setText("已接入当前坦克 · 单人模式"); break;
                case 4: status.setText("联机模式 · 修改功能暂停"); break;
                case -2: status.setText("模块加载失败："+NativeBridge.error); break;
                default: status.setText("模块接入失败 · 请使用 5.1.0 ARM64 版本");
            }
            god.setEnabled(FeatureConfig.GODMODE && (currentState==2 || currentState==3));
            ammo.setEnabled(FeatureConfig.INFINITE_AMMO && (currentState==2 || currentState==3));
            if (panel.getVisibility()==View.VISIBLE) { refreshTanks(); refreshEnemies(); }
            if (waiting) {
                int r=NativeBridge.switchResult();
                if (r!=0) {
                    waiting=false;
                    switch(r) {
                        case 1: result.setText("坦克已替换。"); break;
                        case -1: result.setText("当前坦克尚未就绪（-1），稍等后重试。"); break;
                        case -2: result.setText("载具类型或标签读取失败（-2）。"); break;
                        case -3: result.setText("新载具未生成（-3），请尝试其他车型。"); break;
                        case -4: result.setText("新载具玩家控制器未找到（-4）。"); break;
                        case -5: result.setText("新载具状态引用未就绪（-5）。"); break;
                        case -6: result.setText("对局状态改变，已取消替换。"); break;
                        case -20: result.setText("Hatch 加载失败："+NativeBridge.hatchError()); break;
                        case -21: result.setText("未找到对应的原版载具模板。"); break;
                        case -7: result.setText("新车武器初始化超时，已保留原坦克。"); break;
                        default: result.setText("替换失败（"+r+"）。");
                    }
                } else if(currentState!=3) {waiting=false;result.setText("已离开当前对局，替换取消。");}
            }
            if (waitingEnemy) {
                int r = NativeBridge.spawnEnemyResult();
                if (r != 0) {
                    waitingEnemy = false;
                    switch(r) {
                        case 1: enemyResult.setText("敌人坦克已添加。"); break;
                        case -2: enemyResult.setText("相机或场景接口尚未就绪，请稍后重试。"); break;
                        case -3: enemyResult.setText("屏幕中心没有命中场景，请对准地面。"); break;
                        case -4: enemyResult.setText("指向的表面过陡，请对准地面。"); break;
                        case -5: enemyResult.setText("敌人生成失败，请尝试其他 AI 车型。"); break;
                        case -6: enemyResult.setText("已离开对局，添加敌人已取消。"); break;
                        case -7: enemyResult.setText("坦克生成器尚未就绪，请稍后重试。"); break;
                        case -8: enemyResult.setText("AI 车型列表已改变，请重新选择车型。"); break;
                        default: enemyResult.setText("添加敌人失败（"+r+"）。");
                    }
                }
            }
            swap.setEnabled(FeatureConfig.TANK_SWAP && currentState==3 && currentTanks.length>0 && !waiting && !waitingEnemy);
            spawnEnemy.setEnabled(currentState==3 && currentEnemies.length>0 && !waiting && !waitingEnemy);
        } catch(Throwable failure) {
            status.setText("模块读取失败："+failure.getClass().getSimpleName());
            god.setEnabled(false); ammo.setEnabled(false); swap.setEnabled(false); spawnEnemy.setEnabled(false);
        }
    }
    private void refreshEnemies() {
        if (enemyTank==null || enemyNation==null || !NativeBridge.loaded) return;
        int n = enemyNation.getSelectedItemPosition();
        String[] next = NativeBridge.enemyTanks(n);
        if (next == null) next = new String[0];
        if (n==shownEnemyNation && Arrays.equals(next,currentEnemies)) return;
        shownEnemyNation=n; currentEnemies=next;
        enemyTank.setAdapter(adapter(next.length==0 ? new String[]{"进入单人对局后读取 AI 车型"} : next));
    }
    private void toast(String text) { Toast.makeText(activity,text,Toast.LENGTH_SHORT).show(); }
    void detach() { stopped=true; handler.removeCallbacks(poll); }
}




