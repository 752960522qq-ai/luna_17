package com.hatch.loader;

import android.app.Activity;
import android.view.Gravity;
import android.widget.Button;
import android.widget.FrameLayout;

/** Loader access remains available even when no gameplay module is installed. */
final class LoaderMenu {
    private LoaderMenu() {}
    static void attach(Activity activity) {
        float density=activity.getResources().getDisplayMetrics().density;
        Button button=new Button(activity);
        button.setText("舱盖");
        button.setTextSize(12);
        button.setOnClickListener(v -> HatchLoader.show(activity));
        FrameLayout.LayoutParams layout=new FrameLayout.LayoutParams(
            (int)(72*density),(int)(48*density),Gravity.TOP|Gravity.LEFT);
        layout.leftMargin=(int)(112*density);
        layout.topMargin=(int)(8*density);
        activity.addContentView(button,layout);
    }
}
