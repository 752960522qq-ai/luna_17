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
    private static volatile String report = "舱盖 0.4 正在加载…";
    private static final ModuleSession SESSION = new ModuleSession();
    private static volatile HatchModule module;
    private static File residentNative;
    private static volatile int generation;
    private static final Set<String> loadedTanks = new HashSet<>();
    private static boolean noticeWritten;
    private HatchLoader() {}
    private static File folder(Activity activity) throws IOException {
        File base = activity.getExternalFilesDir(null);
        if (base == null) throw new IOException("游戏文件夹不可用");
        if (!noticeWritten) {
            File notice = new File(base,"RESOURCE_USAGE.txt");
            File temp = File.createTempFile("notice-",".tmp",base);
            try {
                try (InputStream in=activity.getAssets().open("Hatch/RESOURCE_USAGE.txt"); OutputStream out=new FileOutputStream(temp)) {
                    HatchPackage.copy(in,out,16384,null);
                }
                if (!temp.renameTo(notice)) throw new IOException("无法写入资源使用声明");
                noticeWritten=true;
            } finally { temp.delete(); }
        }
        File folder = new File(base, "Hatch/mods");
        if (!folder.isDirectory() && !folder.mkdirs()) throw new IOException("无法创建模组文件夹");
        return folder;
    }
    interface Prepared { void complete(String failure); }
    static void prepare(Activity activity, Prepared callback) {
        IO.execute(() -> {
            String failure = null;
            try {
                if (module == null) {
                    ModuleSession.Loaded resident = SESSION.prepare(() -> {
                        // Resolve the engine through the app class loader, before Unity starts.
                        System.loadLibrary("il2cpp");
                        File mods = folder(activity);
                        HatchPackage core = installCore(activity,mods);
                        if (core == null) return null;
                        File cache = new File(activity.getCodeCacheDir(), "Hatch/" + core.manifest.getString("dex_sha256") + core.manifest.getString("native_sha256"));
                        if (!cache.isDirectory() && !cache.mkdirs()) throw new IOException("无法创建模块缓存");
                        File dex = publish(core,cache,"module.dex","dex_sha256","dex_bytes");
                        File nativeFile = publish(core,cache,"module.so","native_sha256","native_bytes");
                        DexClassLoader loader = new DexClassLoader(dex.getAbsolutePath(),cache.getAbsolutePath(),activity.getApplicationInfo().nativeLibraryDir,HatchLoader.class.getClassLoader());
                        HatchModule loaded = (HatchModule)loader.loadClass(core.manifest.getString("entry_class")).newInstance();
                        if (loaded.apiVersion() != 2) throw new IOException("前置 API 版本不兼容");
                        return new ModuleSession.Loaded(loaded,nativeFile,loader);
                    });
                    if (resident != null) {
                        residentNative = resident.library;
                        module = resident.module;
                    }
                }
            } catch (Exception | LinkageError e) { failure = e.getClass().getSimpleName()+": "+e.getMessage(); }
            String result = failure;
            MAIN.post(() -> callback.complete(result));
        });
    }
    private static File publish(HatchPackage core, File cache, String name, String sha, String size) throws Exception {
        File target = new File(cache,name), temp = File.createTempFile("code-",".tmp",cache);
        try {
            core.extract(name,sha,size,temp);
            if (!temp.setReadOnly()) throw new IOException("无法保护模块文件");
            if (!temp.renameTo(target)) throw new IOException("模块安装失败");
            return target;
        } finally { temp.delete(); }
    }
    private static HatchPackage installCore(Activity activity, File mods) throws Exception {
        File target=new File(mods,"tankinvincible3000.hatch");
        if (target.isFile()) {
            HatchPackage external=HatchPackage.inspect(target);
            if (!"tankinvincible3000".equals(external.id) || !"module".equals(external.type)) throw new IOException("外部前置包无效");
            return external;
        }
        InputStream bundled;
        try { bundled=activity.getAssets().open("Hatch/mods/tankinvincible3000.hatch"); }
        catch (FileNotFoundException absent) { return null; }
        File temp = File.createTempFile("core-",".tmp",mods);
        try {
            try (InputStream in=bundled; OutputStream out=new FileOutputStream(temp)) {
                HatchPackage.copy(in,out,HatchPackage.MAX_BYTES,null);
            }
            HatchPackage builtIn=HatchPackage.inspect(temp);
            if (!"tankinvincible3000".equals(builtIn.id) || !"module".equals(builtIn.type)) throw new IOException("内置前置包无效");
            // Seed only a missing prerequisite. Imported updates belong to the user.
            if (!temp.renameTo(target)) throw new IOException("无法更新必备前置");
            File[] peers=mods.listFiles((d,n)->n.endsWith(".hatch"));
            if (peers!=null) for(File peer:peers) if(!peer.equals(target)) {
                try { if(builtIn.id.equals(HatchPackage.inspect(peer).id)) peer.delete(); } catch(Exception ignored) {}
            }
            return HatchPackage.inspect(target);
        } finally { temp.delete(); }
    }
    public static void start(Activity activity) {
        final int session = ++generation;
        LoaderMenu.attach(activity);
        try { if (module != null) module.start(activity,residentNative); }
        catch (Exception e) { report="前置恢复失败: "+e.getMessage(); show(activity); return; }
        IO.execute(() -> scan(activity,session));
    }
    private static void scan(Activity activity, int session) {
        StringBuilder log = new StringBuilder(); List<HatchPackage> tanks = new ArrayList<>(); HatchPackage core = null;
        try {
            File mods = folder(activity); seed(activity, mods, log);
            File[] files = mods.listFiles((d,n) -> n.endsWith(".hatch"));
            if (files == null) throw new IOException("无法读取模组文件夹");
            Arrays.sort(files); Set<String> ids = new HashSet<>(); Set<String> duplicates=new HashSet<>();
            for (File file : files) {
                try {
                    HatchPackage pack = HatchPackage.inspect(file);
                    if (!ids.add(pack.id)) { duplicates.add(pack.id); throw new IOException("重复模组 ID: " + pack.id); }
                    if (pack.type.equals("module")) core = pack;
                    else { if (tanks.size() >= 16) throw new IOException("最多加载 16 个内容包"); tanks.add(pack); }
                } catch (Exception e) { log.append("✗ ").append(file.getName()).append(": ").append(e.getMessage()).append('\n'); }
            }
            if (!duplicates.isEmpty())throw new IOException("重复模组 ID，已停止加载: "+duplicates);
            if (core == null || module == null) {
                report="舱盖 0.4 · 空白调试包\n尚未加载坦无敌3000。原版游戏可正常启动。\n\n已发现 " + tanks.size() + " 个坦克包；导入坦无敌3000 1.0 前置并完全退出重启后，才能加载坦克模组。\n\n" + log;
                return;
            }
            HatchModule loaded = module;
            log.append("✓ 坦无敌3000 1.0（前置）\n"); int count = 0;
            Map<String,HatchPackage> packages = new HashMap<>();
            List<DependencyOrder.Node> nodes = new ArrayList<>();
            List<HatchPackage> discovered = new ArrayList<>(tanks); discovered.add(core);
            for (HatchPackage pack : discovered) {
                Map<String,String> requires = new HashMap<>();
                JSONObject deps = pack.manifest.optJSONObject("requires");
                if (deps != null) { Iterator<String> keys=deps.keys(); while(keys.hasNext()) { String key=keys.next(); requires.put(key,deps.getString(key)); } }
                nodes.add(new DependencyOrder.Node(pack.id,pack.manifest.optString("version","1.0"),requires)); packages.put(pack.id,pack);
            }
            tanks.clear();
            for(String id : DependencyOrder.resolve(nodes)) if(!id.equals(core.id)) tanks.add(packages.get(id));
            Set<String> successful = new HashSet<>(loadedTanks); successful.add(core.id);
            for (HatchPackage tank : tanks) {
                if (session != generation) return;
                if (loadedTanks.contains(tank.id)) { log.append("✓ ").append(tank.name).append("（已加载）\n"); count++; continue; }
                File runtime = File.createTempFile("hatch-", ".bin", activity.getCacheDir());
                try {
                    JSONObject requires = tank.manifest.optJSONObject("requires");
                    if (requires != null) { Iterator<String> keys=requires.keys(); while(keys.hasNext()) { String id=keys.next(); if(!successful.contains(id))throw new IOException("依赖加载失败: "+id); } }
                    String failure;
                    if(tank.type.equals("gameplay")) {
                        if(!(loaded instanceof HatchFeatureHost))throw new IOException("前置不支持玩法扩展，请更新坦无敌3000");
                        HatchFeatureHost host=(HatchFeatureHost)loaded;
                        Set<String> supported=new HashSet<>(Arrays.asList(host.capabilities()));
                        JSONArray needed=tank.manifest.getJSONArray("capabilities");
                        for(int i=0;i<needed.length();i++) if(!supported.contains(needed.getString(i)))throw new IOException("缺少扩展能力: "+needed.getString(i));
                        tank.extract("features.json","features_sha256","features_bytes",runtime);
                        ByteArrayOutputStream bytes=new ByteArrayOutputStream();
                        try(InputStream in=new FileInputStream(runtime)){HatchPackage.copy(in,bytes,65536,null);}
                        JSONObject configuration=new JSONObject(bytes.toString("UTF-8"));
                        if(configuration.has("voiceDirectory"))throw new IOException("语音路径只能由加载器提供");
                        if(tank.manifest.has("voices_bytes"))configuration.put("voiceDirectory",tank.extractVoices(activity.getCacheDir()).getAbsolutePath());
                        failure=host.loadFeatures(tank.id,configuration.toString());
                    } else {
                        tank.extract("runtime.bin","runtime_sha256","runtime_bytes",runtime);
                        JSONObject configuration=new JSONObject(tank.manifest.toString());
                        // Legacy .hatch files already include weapon.json. Read that
                        // source without rewriting or trusting it as executable code.
                        if(!configuration.has("shell_filling_grams")){
                            try(java.util.zip.ZipFile archive=new java.util.zip.ZipFile(tank.archive)){
                                java.util.zip.ZipEntry entry=archive.getEntry("weapon.json");
                                if(entry!=null){
                                    ByteArrayOutputStream bytes=new ByteArrayOutputStream();
                                    try(InputStream in=archive.getInputStream(entry)){HatchPackage.copy(in,bytes,65536,null);}
                                    JSONObject shells=new JSONObject(bytes.toString("UTF-8")).optJSONObject("shells");
                                    JSONObject filling=new JSONObject();
                                    if(shells!=null)for(String shell:new String[]{"AP","HE","APCR","WP","HEAT"}){
                                        JSONObject ammo=shells.optJSONObject(shell);
                                        if(ammo!=null){
                                            if(ammo.has("explosiveMassGrams"))filling.put(shell,ammo.getDouble("explosiveMassGrams"));
                                            else if(ammo.has("explosiveMassKg"))filling.put(shell,ammo.getDouble("explosiveMassKg")*1000);
                                        }
                                    }
                                    if(filling.length()>0)configuration.put("shell_filling_grams",filling);
                                }
                            }
                        }
                        failure=loaded.loadTank(runtime,configuration.toString());
                    }
                    if (failure == null || !failure.isEmpty()) throw new IOException(failure == null ? "加载失败" : failure);
                    loadedTanks.add(tank.id); successful.add(tank.id);
                    log.append("✓ ").append(tank.name).append(tank.manifest.has("magazine") ? "（弹匣炮）" : "").append('\n'); count++;
                } catch (Exception e) { log.append("✗ ").append(tank.name).append(": ").append(e.getMessage()).append('\n'); }
                finally { runtime.delete(); }
            }
            report = "舱盖 0.4\n已加载前置及 " + count + " 个模组\n\n" + log + "\n导入或更新后，完全退出并重新打开游戏。";
        } catch (Exception | LinkageError e) {
            report = "舱盖 0.4 加载失败：" + e.getMessage() + "\n\n" + log;
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
        new AlertDialog.Builder(activity).setTitle("舱盖 Hatch 0.4").setMessage(report)
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
