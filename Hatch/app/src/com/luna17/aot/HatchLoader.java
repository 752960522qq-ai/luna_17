package com.luna17.aot;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.net.Uri;
import android.widget.Toast;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.zip.*;
import org.json.JSONObject;

/** Data-only tank packages. New imports become active on the next process start. */
final class HatchLoader {
    static final int PICK = 7301;
    private static final long MAX = 256L*1024*1024;
    private static final ExecutorService IO = Executors.newSingleThreadExecutor();
    private static volatile String report = "正在扫描坦克包…";
    private static volatile boolean started;
    private static File folder(Activity a) throws IOException {
        File base=a.getExternalFilesDir(null);
        if(base==null)throw new IOException("游戏文件夹暂不可用");
        File f=new File(base,"Hatch/mods");
        if(!f.isDirectory()&&!f.mkdirs())throw new IOException("无法创建 Hatch/mods");
        return f;
    }
    static synchronized void start(final Activity a) {
        if(started)return;started=true;
        final android.content.Context context=a.getApplicationContext();
        IO.execute(new Runnable(){public void run(){
            StringBuilder log=new StringBuilder();int count=0;
            try {
                File f=folder(a);log.append(f.getAbsolutePath()).append("\n\n");
                File[] files=f.listFiles(new FilenameFilter(){public boolean accept(File d,String n){return n.endsWith(".hatch");}});
                if(files==null)throw new IOException("无法读取模组文件夹");
                Arrays.sort(files);Set<String> ids=new HashSet<String>();
                for(File pack:files){
                    try {
                        if(count>=16)throw new IOException("最多加载 16 个坦克包");
                        Package p=validate(pack,context.getCacheDir());
                        if(!ids.add(p.id))throw new IOException("重复坦克 ID: "+p.id);
                        if(!NativeBridge.loaded)throw new IOException("原生模块未就绪");
                        String failure=NativeBridge.loadHatch(p.runtime.getAbsolutePath());
                        p.runtime.delete();
                        if(failure==null||!failure.isEmpty())throw new IOException(failure==null?"加载失败":failure);
                        count++;log.append("✓ ").append(p.name).append(" [").append(p.id).append("]\n");
                    } catch(Exception e){log.append("✗ ").append(pack.getName()).append(": ").append(e.getMessage()).append("\n");}
                }
                report="Hatch · 舱盖 0.1\n已加载 "+count+" 个外置坦克\n\n"+log+"\n导入或更新后，请完全退出并重新打开游戏。";
            } catch(Exception e){report="Hatch 扫描失败: "+e.getMessage();}
        }});
    }
    static void show(final Activity a){
        new AlertDialog.Builder(a).setTitle("Hatch · 舱盖 0.1").setMessage(report)
            .setPositiveButton("导入 .hatch 坦克包",(d,w)->{
                Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*");
                try{a.startActivityForResult(i,PICK);}catch(Exception e){Toast.makeText(a,"无法打开文件选择器",Toast.LENGTH_LONG).show();}
            }).setNegativeButton("关闭",null).show();
    }
    static boolean result(final Activity a,int request,int result,Intent data){
        if(request!=PICK)return false;
        if(result!=Activity.RESULT_OK||data==null||data.getData()==null)return true;
        final Uri uri=data.getData();
        IO.execute(new Runnable(){public void run(){String message;File temp=null;
            try {
                File mods=folder(a);temp=File.createTempFile("import-",".tmp",mods);
                try(InputStream in=a.getContentResolver().openInputStream(uri);OutputStream out=new FileOutputStream(temp)){
                    if(in==null)throw new IOException("无法读取所选文件");copy(in,out,MAX,null);
                }
                Package p=validate(temp,a.getCacheDir());p.runtime.delete();
                File target=new File(mods,p.id+".hatch");
                // POSIX rename on this app-owned filesystem replaces a prior version atomically.
                if(!temp.renameTo(target))throw new IOException("无法保存坦克包");
                message="已导入 "+p.name+"。完全退出并重启游戏后加载。";
            }catch(Exception e){message="导入失败: "+e.getMessage();}finally{if(temp!=null)temp.delete();}
            final String text=message;a.runOnUiThread(()->{if(!a.isFinishing())new AlertDialog.Builder(a).setTitle("Hatch 导入结果").setMessage(text).setPositiveButton("确定",null).show();});
        }});return true;
    }
    private static final class Package {String id,name;File runtime;}
    private static Package validate(File archive,File cache)throws Exception {
        if(archive.length()<=0||archive.length()>MAX)throw new IOException("坦克包大小超限");
        File runtime=null;boolean success=false;
        try(ZipFile z=new ZipFile(archive)){
            Set<String> names=new HashSet<String>();Enumeration<? extends ZipEntry> entries=z.entries();int n=0;
            while(entries.hasMoreElements()){
                ZipEntry e=entries.nextElement();String s=e.getName();
                if(++n>16||e.isDirectory()||s.contains("/")||s.contains("\\")||s.contains("..")||!names.add(s))throw new IOException("包内路径或重复文件非法");
                if(e.getSize()<0||e.getSize()>MAX)throw new IOException("包内文件过大");
            }
            ZipEntry manifest=z.getEntry("hatch.json"),binary=z.getEntry("runtime.bin");
            if(manifest==null||binary==null)throw new IOException("请选择 Hatch 坦克包；.tankpack 需先转换");
            ByteArrayOutputStream bytes=new ByteArrayOutputStream();try(InputStream in=z.getInputStream(manifest)){copy(in,bytes,16384,null);}
            JSONObject m=new JSONObject(new String(bytes.toByteArray(),StandardCharsets.UTF_8));
            if(m.getInt("format")!=1||!"Hatch".equals(m.getString("loader"))||!"0.1".equals(m.getString("loader_version"))||!"5.1.0".equals(m.getString("game_version"))||!"arm64-v8a".equals(m.getString("abi")))throw new IOException("包格式或游戏版本不兼容");
            String id=m.getString("id");if(!id.matches("[A-Za-z0-9_-]{1,48}"))throw new IOException("坦克 ID 非法");
            String expected=m.getString("runtime_sha256");if(!expected.matches("[a-f0-9]{64}"))throw new IOException("缺少校验值");
            runtime=File.createTempFile("hatch-",".bin",cache);MessageDigest sha=MessageDigest.getInstance("SHA-256");long size;
            try(InputStream in=z.getInputStream(binary);OutputStream out=new FileOutputStream(runtime)){size=copy(in,out,MAX,sha);}
            StringBuilder digest=new StringBuilder();for(byte b:sha.digest())digest.append(String.format(Locale.ROOT,"%02x",b&255));
            if(!expected.equals(digest.toString())||size!=m.getLong("runtime_bytes"))throw new IOException("坦克包内容校验失败");
            try(RandomAccessFile in=new RandomAccessFile(runtime,"r")){
                byte[] h=new byte[88];in.readFully(h);byte[] magic={'H','A','T','C','H','0','1',0};
                for(int i=0;i<8;i++)if(h[i]!=magic[i])throw new IOException("运行时头部非法");
                java.nio.ByteBuffer header=java.nio.ByteBuffer.wrap(h).order(java.nio.ByteOrder.LITTLE_ENDIAN);
                if(header.getInt(8)!=1||Integer.toUnsignedLong(header.getInt(12))!=size)throw new IOException("运行时长度非法");
                int end=24;while(end<88&&h[end]!=0)end++;
                if(end==88||!id.equals(new String(h,24,end-24,StandardCharsets.UTF_8)))throw new IOException("坦克 ID 不一致");
            }
            Package p=new Package();p.id=id;p.name=m.getString("name");p.runtime=runtime;success=true;return p;
        }finally{if(!success&&runtime!=null)runtime.delete();}
    }
    private static long copy(InputStream in,OutputStream out,long max,MessageDigest sha)throws IOException {
        byte[] b=new byte[65536];long size=0;int n;
        while((n=in.read(b))!=-1){if((size+=n)>max)throw new IOException("文件超过大小限制");out.write(b,0,n);if(sha!=null)sha.update(b,0,n);}return size;
    }
}
