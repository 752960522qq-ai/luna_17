package com.hatch.loader;

import android.app.*;
import android.content.*;
import android.net.Uri;
import android.os.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.*;
import dalvik.system.DexClassLoader;
import org.json.*;

public final class HatchLoader {
    private static final int PICK = 7301;
    private static final ExecutorService IO = Executors.newSingleThreadExecutor();
    private static final Handler MAIN = new Handler(Looper.getMainLooper());
    private static volatile String report = "舱盖 0.2 正在加载…";
    private static HatchModule module;
    private static File residentNative;
    private static volatile int generation;
    private HatchLoader() {}
    private static File folder(Activity activity) throws IOException {
        File base = activity.getExternalFilesDir(null);
        if (base == null) throw new IOException("游戏文件夹不可用");
        File folder = new File(base, "Hatch/mods");
        if (!folder.isDirectory() && !folder.mkdirs()) throw new IOException("无法创建模组文件夹");
        return folder;
    }
    public static void start(Activity activity) {
        final int session = ++generation;
        if (module != null) {
            try { module.start(activity,residentNative); } catch (Exception e) { report="前置恢复失败: "+e.getMessage(); show(activity); }
            return;
        }
        IO.execute(() -> scan(activity, session));
    }
    private static void scan(Activity activity, int session) {
        StringBuilder log = new StringBuilder(); List<HatchPackage> tanks = new ArrayList<>(); HatchPackage core = null;
        try {
            File mods = folder(activity); seed(activity, mods, log);
            File[] files = mods.listFiles((d,n) -> n.endsWith(".hatch"));
            if (files == null) throw new IOException("无法读取模组文件夹");
            Arrays.sort(files); Set<String> ids = new HashSet<>();
            for (File file : files) {
                try {
                    HatchPackage pack = HatchPackage.inspect(file);
                    if (!ids.add(pack.id)) throw new IOException("重复模组 ID: " + pack.id);
                    if (pack.type.equals("module")) core = pack;
                    else { if (tanks.size() >= 16) throw new IOException("最多加载 16 个坦克包"); tanks.add(pack); }
                } catch (Exception e) { log.append("✗ ").append(file.getName()).append(": ").append(e.getMessage()).append('\n'); }
            }
            if (core == null) throw new IOException("缺少必备前置：坦无敌3000 1.0");
            File cache = new File(activity.getCodeCacheDir(), "Hatch/" + core.manifest.getString("dex_sha256") + core.manifest.getString("native_sha256"));
            if (!cache.isDirectory() && !cache.mkdirs()) throw new IOException("无法创建模块缓存");
            File dex = new File(cache,"module.dex"), nativeFile = new File(cache,"module.so");
            // Re-extract to temporary writable files, then publish immutable code.
            File tempDex = new File(cache,"module.dex.tmp"), tempNative = new File(cache,"module.so.tmp");
            core.extract("module.dex","dex_sha256","dex_bytes",tempDex); core.extract("module.so","native_sha256","native_bytes",tempNative);
            if (!tempDex.setReadOnly() || !tempNative.setReadOnly()) throw new IOException("无法保护模块文件");
            dex.delete(); nativeFile.delete();
            if (!tempDex.renameTo(dex) || !tempNative.renameTo(nativeFile)) throw new IOException("模块安装失败");
            DexClassLoader loader = new DexClassLoader(dex.getAbsolutePath(), cache.getAbsolutePath(), null, HatchLoader.class.getClassLoader());
            HatchModule loaded = (HatchModule) loader.loadClass(core.manifest.getString("entry_class")).newInstance();
            if (loaded.apiVersion() != 2) throw new IOException("前置 API 版本不兼容");
            CountDownLatch started = new CountDownLatch(1); Throwable[] error = new Throwable[1];
            MAIN.post(() -> { try { if (session != generation || activity.isFinishing()) throw new IOException("加载已取消"); loaded.start(activity,nativeFile); residentNative=nativeFile; module = loaded; } catch (Throwable t) { error[0]=t; } finally { started.countDown(); } });
            if (!started.await(30,TimeUnit.SECONDS)) throw new IOException("前置启动超时");
            if (error[0] != null) throw new IOException("前置启动失败: " + error[0].getMessage());
            log.append("✓ 坦无敌3000 1.0（前置）\n"); int count = 0;
            for (HatchPackage tank : tanks) {
                if (session != generation) return;
                File runtime = File.createTempFile("hatch-", ".bin", activity.getCacheDir());
                try {
                    JSONObject requires = tank.manifest.optJSONObject("requires");
                    if (requires != null && !"1.0".equals(requires.optString("tankinvincible3000","1.0"))) throw new IOException("前置版本不兼容");
                    tank.extract("runtime.bin","runtime_sha256","runtime_bytes",runtime);
                    String failure = loaded.loadTank(runtime,tank.manifest.toString());
                    if (failure == null || !failure.isEmpty()) throw new IOException(failure == null ? "加载失败" : failure);
                    log.append("✓ ").append(tank.name).append(tank.manifest.has("magazine") ? "（弹匣炮）" : "").append('\n'); count++;
                } catch (Exception e) { log.append("✗ ").append(tank.name).append(": ").append(e.getMessage()).append('\n'); }
                finally { runtime.delete(); }
            }
            report = "舱盖 0.2\n已加载前置及 " + count + " 个坦克包\n\n" + log + "\n导入或更新后，完全退出并重新打开游戏。";
        } catch (Exception | LinkageError e) {
            report = "舱盖 0.2 加载失败：" + e.getMessage() + "\n\n" + log;
            MAIN.post(() -> { if (session == generation && !activity.isFinishing()) show(activity); });
        }
    }
    private static void seed(Activity activity, File mods, StringBuilder log) throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (InputStream in = activity.getAssets().open("Hatch/catalog.json")) { HatchPackage.copy(in,bytes,16384,null); }
        JSONArray catalog = new JSONObject(bytes.toString("UTF-8")).getJSONArray("mods");
        Set<String> present = new HashSet<>(); File[] files = mods.listFiles((d,n) -> n.endsWith(".hatch"));
        if (files != null) for (File file : files) try { present.add(HatchPackage.inspect(file).id); } catch (Exception ignored) {}
        SharedPreferences prefs = activity.getSharedPreferences("Hatch-builtin-seeds-02",0);
        for (int i=0;i<catalog.length();i++) {
            JSONObject item = catalog.getJSONObject(i); String id = item.getString("id");
            if (!id.matches("[A-Za-z0-9_-]{1,48}")) throw new IOException("内置 ID 非法");
            if (present.contains(id) || prefs.getBoolean(id,false)) continue;
            File temp = File.createTempFile("seed-",".tmp",mods);
            try {
                try (InputStream in=activity.getAssets().open("Hatch/mods/"+id+".hatch"); OutputStream out=new FileOutputStream(temp)) { HatchPackage.copy(in,out,HatchPackage.MAX_BYTES,null); }
                HatchPackage pack = HatchPackage.inspect(temp); if (!id.equals(pack.id)) throw new IOException("内置 ID 不一致");
                if (!temp.renameTo(new File(mods,id+".hatch"))) throw new IOException("无法释放内置模组");
                prefs.edit().putBoolean(id,true).commit(); present.add(id);
            } finally { temp.delete(); }
        }
    }
    public static void show(Activity activity) {
        new AlertDialog.Builder(activity).setTitle("舱盖 Hatch 0.2").setMessage(report)
            .setPositiveButton("导入 .hatch", (d,w) -> { Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*"); activity.startActivityForResult(intent,PICK); })
            .setNegativeButton("关闭",null).show();
    }
    public static boolean result(Activity activity,int request,int result,Intent data) {
        if (request != PICK) return false;
        if (result != Activity.RESULT_OK || data == null || data.getData() == null) return true;
        Uri uri = data.getData();
        IO.execute(() -> {
            String message; File temp = null;
            try {
                File mods=folder(activity); temp=File.createTempFile("import-",".tmp",mods);
                try (InputStream in=activity.getContentResolver().openInputStream(uri); OutputStream out=new FileOutputStream(temp)) {
                    if (in == null) throw new IOException("无法读取所选文件"); HatchPackage.copy(in,out,HatchPackage.MAX_BYTES,null);
                }
                HatchPackage pack=HatchPackage.inspect(temp); File target=new File(mods,pack.id+".hatch");
                // Remove aliases with the same ID so updating a renamed package cannot create duplicates.
                File[] peers=mods.listFiles((d,n)->n.endsWith(".hatch"));
                if (!temp.renameTo(target)) throw new IOException("无法保存模组");
                if (peers != null) for (File peer:peers) if (!peer.equals(target)) try { if (pack.id.equals(HatchPackage.inspect(peer).id)) peer.delete(); } catch (Exception ignored) {}
                message="已导入 "+pack.name+"。完全退出并重启游戏后加载。";
            } catch (Exception e) { message="导入失败: "+e.getMessage(); } finally { if (temp != null) temp.delete(); }
            String text=message; MAIN.post(() -> { if (!activity.isFinishing()) new AlertDialog.Builder(activity).setTitle("舱盖导入结果").setMessage(text).setPositiveButton("确定",null).show(); });
        }); return true;
    }
    static void stop() { generation++; if (module != null) { module.stop(); } }
}
