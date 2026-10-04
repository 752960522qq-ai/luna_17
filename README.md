# Attack on Tank 5.1.0 · luna_17

基于用户提供的原始 `Attack on Tank _ Rush_5.1.0.apks`，生成带游戏内悬浮菜单的 ARM64 APK 测试版。

菜单包含无敌、无限弹药、对局换坦克。进入游戏后点击左上角 **MOD**，可拖动按钮；换坦克按国家与场景中的实际车型列表选择，保留位置和朝向，并更新玩家、界面与镜头引用。修改功能只在单人模式启用，联机模式自动暂停。

## 安装

适用于 Android 9 及以上的 ARM64 设备，不需要 root 或系统悬浮窗权限。APK 使用独立的开发签名，无法覆盖安装原版。先备份需要保留的存档，再卸载原版并安装测试 APK。安装后进入单人对局，菜单应显示“已接入当前坦克”。

当前交付为 **r2 修复版**，与此前测试 APK 签名一致，可直接覆盖更新，无须卸载此前测试版。

r2 修复了对局换坦克显示“替换未完成（-3）”的问题：游戏的 `_GenerateUnit` 第一个业务参数要求 `System.String` 标签 `"Player"`，此前传入了 `System.Type` 对象，导致游戏拒绝生成新载具。现在复用游戏生成玩家载具时使用的同一个标签，并区分失败提示。

此前测试 APK 已由用户在安卓单人对局中确认能够启动并接入当前坦克。r2 已完成 APK 签名和结构检查，以及六项 ARM64 执行验证；**r2 的换车、移动、瞄准和开火仍需安卓真机验证**。

## 实现

- `app/src`：继承原游戏 `UnityPlayerActivity` 的启动 Activity 和原生 Android 菜单。
- `native/aotmod.c`、`native/guards.S`：版本匹配、指令跳转、玩家伤害拦截、使用游戏自身加密整数转换函数补弹、在 Unity 主线程替换坦克。
- `profiles/attack-on-tank-5.1.0.json`：原库及元数据 SHA-256、方法 RVA、原始指令和字段偏移。
- `scripts/repack.py`：编辑二进制 Manifest，合并 ARM64 split，保留原资源、DEX、游戏库与元数据。
- `scripts/decode_sections.py`：解密此版本的七个受保护元数据区段，供后续分析。

原游戏包、游戏二进制、签名私钥和密码不存放在仓库中。不能直接把这些偏移用于其他游戏版本。

## 构建

需要 Linux x86-64、JDK 17+、Android NDK、`android.jar`、R8/D8 JAR 和 `apksigner.jar`。将原始 APKS 留在仓库外。签名密钥可复用已有开发密钥，也可省略 `--keystore` 和 `--password-file`，让脚本在本地生成。请保留密钥以便以后覆盖更新测试版。

```bash
python scripts/build.py \
  --apks /path/to/original.apks \
  --ndk /path/to/android-ndk \
  --android-jar /path/to/android.jar \
  --r8 /path/to/r8.jar \
  --apksigner /path/to/apksigner.jar \
  --keystore /path/to/development.jks \
  --password-file /path/to/password.txt \
  --output dist/Attack-on-Tank-5.1.0-luna17-r2.apk
```

`app/stubs` 只用于编译；打包时不会加入假的 Unity Activity。APK 的原始游戏库和元数据必须匹配 profile 中的指纹，否则构建中止。

## 验证

```bash
python -m pip install -r requirements-dev.txt
python tests/test_native.py --module build/libaotmod.so --game-library /path/to/original/libil2cpp.so --report build/native-tests.json
python scripts/verify.py --apk dist/Attack-on-Tank-5.1.0-luna17-r2.apk --apks /path/to/original.apks --native-test-report build/native-tests.json
java -jar /path/to/apksigner.jar verify --verbose dist/Attack-on-Tank-5.1.0-luna17-r2.apk
```

原生测试执行实际编译后的 ARM64 指令，覆盖玩家/敌方伤害区分、参数保留、原游戏 ObscuredInt 转换函数与数组边界、ADRP 重定位，以及换坦克的位置、朝向、玩家和镜头引用更新。换车验证直接执行原游戏 `_GenerateUnit` 和字符串比较指令，复现错误类型参数被拒绝，并检查六国玩家车型选择。Unity 实例化及场景行为仍需设备实测。当前交付包的校验记录见 `verification.json`。
