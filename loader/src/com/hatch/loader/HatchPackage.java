package com.hatch.loader;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.security.MessageDigest;
import java.util.*;
import java.util.zip.*;
import org.json.JSONObject;

final class HatchPackage {
    static final long MAX_BYTES = 256L * 1024 * 1024;
    final File archive;
    final JSONObject manifest;
    final String id, name, type;
    private HatchPackage(File file, JSONObject doc) throws Exception {
        archive = file; manifest = doc;
        id = doc.getString("id"); name = doc.getString("name");
        type = doc.optString("type", "tank");
        if (!id.matches("[A-Za-z0-9_-]{1,48}")) throw new IOException("模组 ID 非法");
        int format = doc.getInt("format");
        if (format != 1 && format != 2) throw new IOException("不支持的包格式");
        if (!"Hatch".equals(doc.getString("loader")) ||
                !("0.1".equals(doc.getString("loader_version")) || "0.2".equals(doc.getString("loader_version"))) ||
                !"5.1.0".equals(doc.getString("game_version")) || !"arm64-v8a".equals(doc.getString("abi")))
            throw new IOException("游戏或加载器版本不兼容");
        if (!type.equals("tank") && !type.equals("module")) throw new IOException("不支持的模组类型");
        if (type.equals("module") && (format != 2 || doc.getInt("api_version") != 2 ||
                !id.equals("tankinvincible3000") || !"1.0".equals(doc.getString("version"))))
            throw new IOException("前置模组接口不兼容");
        if (type.equals("tank") && id.equals("tankinvincible3000")) throw new IOException("坦克不能使用前置模组 ID");
        if (type.equals("module") && !"com.luna17.aot.TankInvincibleModule".equals(doc.getString("entry_class")))
            throw new IOException("前置入口不兼容");
        JSONObject requires = doc.optJSONObject("requires");
        if (requires != null) {
            Iterator<String> keys = requires.keys();
            while (keys.hasNext()) {
                String key = keys.next();
                if (!"tankinvincible3000".equals(key) || !"1.0".equals(requires.getString(key)))
                    throw new IOException("不支持的前置依赖: " + key);
            }
        }
        JSONObject magazine = doc.optJSONObject("magazine");
        if (magazine != null) {
            double rawCapacity = magazine.getDouble("capacity");
            int capacity = magazine.getInt("capacity");
            double interval = magazine.getDouble("shotInterval"), reload = magazine.getDouble("reloadTime");
            if (rawCapacity != capacity || capacity < 2 || capacity > 200 || !Double.isFinite(interval) || interval < .03 || interval > 60 ||
                    !Double.isFinite(reload) || reload < interval || reload > 300)
                throw new IOException("弹匣容量或装填时间无效");
        }
    }
    static HatchPackage inspect(File archive) throws Exception {
        if (archive.length() <= 0 || archive.length() > MAX_BYTES) throw new IOException("模组大小超限");
        try (ZipFile zip = new ZipFile(archive)) {
            Enumeration<? extends ZipEntry> entries = zip.entries(); Set<String> names = new HashSet<>();
            long total = 0;
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement(); String name = entry.getName();
                if (names.size() >= 16 || entry.isDirectory() || name.contains("/") || name.contains("\\") ||
                        name.contains("..") || !names.add(name) || entry.getSize() < 0 || entry.getSize() > MAX_BYTES)
                    throw new IOException("模组文件结构无效");
                total += entry.getSize(); if (total > MAX_BYTES) throw new IOException("解压大小超限");
            }
            ZipEntry doc = zip.getEntry("hatch.json"); if (doc == null) throw new IOException("缺少 hatch.json");
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            try (InputStream in = zip.getInputStream(doc)) { copy(in, bytes, 16384, null); }
            HatchPackage pack = new HatchPackage(archive, new JSONObject(new String(bytes.toByteArray(), StandardCharsets.UTF_8)));
            if (pack.type.equals("tank")) {
                pack.verify(zip, "runtime.bin", "runtime_sha256", "runtime_bytes", null);
                byte[] header = new byte[88];
                try (DataInputStream in = new DataInputStream(zip.getInputStream(zip.getEntry("runtime.bin")))) { in.readFully(header); }
                ByteBuffer runtime = ByteBuffer.wrap(header).order(ByteOrder.LITTLE_ENDIAN);
                int end = 24; while (end < 88 && header[end] != 0) end++;
                if (!Arrays.equals(Arrays.copyOf(header,8), new byte[]{'H','A','T','C','H','0','1',0}) ||
                        runtime.getInt(8) != 1 || runtime.getInt(12) != pack.manifest.getLong("runtime_bytes") ||
                        runtime.getInt(16) < 4 || runtime.getInt(16) > 2048 || runtime.getInt(20) < 0 || runtime.getInt(20) > 128 ||
                        !pack.id.equals(new String(header,24,end-24,StandardCharsets.US_ASCII)))
                    throw new IOException("坦克运行数据与清单不一致");
            }
            else {
                pack.verify(zip, "module.dex", "dex_sha256", "dex_bytes", null);
                pack.verify(zip, "module.so", "native_sha256", "native_bytes", null);
            }
            return pack;
        }
    }
    File extract(String entry, String hash, String size, File output) throws Exception {
        try (ZipFile zip = new ZipFile(archive)) { verify(zip, entry, hash, size, output); }
        return output;
    }
    private void verify(ZipFile zip, String entryName, String hashKey, String sizeKey, File output) throws Exception {
        ZipEntry entry = zip.getEntry(entryName); if (entry == null) throw new IOException("缺少 " + entryName);
        String expected = manifest.getString(hashKey); if (!expected.matches("[a-f0-9]{64}")) throw new IOException("校验值无效");
        MessageDigest hash = MessageDigest.getInstance("SHA-256");
        OutputStream sink = output == null ? new OutputStream() { public void write(int b) {} public void write(byte[] b,int o,int n) {} } : new FileOutputStream(output);
        long count;
        try (InputStream in = zip.getInputStream(entry); OutputStream out = sink) { count = copy(in, out, MAX_BYTES, hash); }
        if (count != manifest.getLong(sizeKey) || !expected.equals(hex(hash.digest()))) {
            if (output != null) output.delete(); throw new IOException(entryName + " 内容校验失败");
        }
    }
    static String hex(byte[] bytes) {
        StringBuilder value = new StringBuilder(); for (byte b : bytes) value.append(String.format(Locale.ROOT,"%02x", b & 255));
        return value.toString();
    }
    static long copy(InputStream in, OutputStream out, long limit, MessageDigest hash) throws IOException {
        byte[] buffer = new byte[65536]; long total = 0; int count;
        while ((count = in.read(buffer)) != -1) {
            total += count; if (total > limit) throw new IOException("文件超过大小限制");
            out.write(buffer, 0, count); if (hash != null) hash.update(buffer, 0, count);
        }
        return total;
    }
}
