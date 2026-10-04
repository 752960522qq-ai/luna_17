# Attack on Tank 5.1.0 · luna_17

基于用户提供的原始 `Attack on Tank _ Rush_5.1.0.apks`，生成带游戏内悬浮菜单的 ARM64 APK 测试版。

菜单包含无敌、无限弹药、对局换坦克。进入游戏后点击左上角 **MOD**，可拖动按钮；换坦克按国家与场景中的实际车型列表选择，保留位置和朝向，并更新玩家、界面与镜头引用。修改功能只在单人模式启用，联机模式自动暂停。

当前工程为 **TankInvincible_3000 1.1.0-dev / 修改器 r4**。构建器支持版本、资源和 18 项关键方法指纹检查，签名重建及更新草案；增加已审核的 T‑54 (1949) 玩家 Tank Pack 注入。使用方法见 [BUILDER_GUIDE.md](BUILDER_GUIDE.md)，历史见 [CHANGELOG.md](CHANGELOG.md)，本次修复与验证见 [T54_R4_REPORT.md](T54_R4_REPORT.md)。

## 安装

适用于 Android 9 及以上的 ARM64 设备，不需要 root 或系统悬浮窗权限。APK 使用独立的开发签名，无法覆盖安装原版。先备份需要保留的存档，再卸载原版并安装测试 APK。安装后进入单人对局，菜单应显示“已接入当前坦克”。

当前交付为 **r4 / T‑54 测试版**，与此前测试 APK 签名一致，可覆盖更新此前修改版。

r3 修复了对局换坦克显示“新载具缺少控制组件（-4）”的问题：原游戏的 `T34_85_Player` 和 `ZiS_3_Player` 预制体根对象包含 `PlayerControl`，但 `UnitStatus` 在子对象 `Unit Info` 上。此前只在根对象查找 `UnitStatus`，因此误判组件缺失。现在从新控制器的 `uStatus`（偏移 `0x70`）读取游戏已序列化的状态引用，确认控制器和状态仍有效后再更新玩家和镜头。失败时保留原坦克，并区分控制器缺失（-4）和状态引用未就绪（-5）。

r3 保留 r2 的生成参数修复：游戏的 `_GenerateUnit` 第一个业务参数要求 `System.String` 标签 `"Player"`，因此复用游戏生成玩家载具时使用的同一个标签。

本次修复在新车武器初始化完成后接管玩家，保留对局阵营与碰撞层，并重置瞄准弹速缓存。进入单人对局后，在 MOD 菜单选择“苏联 → T54_1949_Player → 替换当前坦克”。T‑54 暂时只供玩家使用。

r4 已通过 11 项 ARM64 回归、10 项构建器回归、资源保存后重读和 APK 签名/结构检查。**游戏内伤害、敌我识别、离线重启、履带、悬挂及音效仍需安卓真机确认**。离线启动处理未声明能覆盖所有篡改告警来源。

## 实现

- `app/src`：继承原游戏 `UnityPlayerActivity` 的启动 Activity 和原生 Android 菜单。
- `native/aotmod.c`、`native/guards.S`：版本匹配、指令跳转、玩家伤害拦截、使用游戏自身加密整数转换函数补弹、在 Unity 主线程替换坦克。
- `profiles/attack-on-tank-5.1.0.json`：原库及元数据 SHA-256、方法 RVA、原始指令和字段偏移。
- `scripts/repack.py`：编辑二进制 Manifest、合并 ARM64 split，按资源报告写入派生 data.unity3d，保留原 DEX、游戏库与元数据。
- `tankbuilder/modelrig.py`、`tankbuilder/unity_assets.py`：生成独立炮塔、后坐、履带与悬挂节点，写入网格/贴图和玩家预制体。
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
  --zipalign /path/to/zipalign \
  --keystore /path/to/development.jks \
  --password-file /path/to/password.txt \
  --output dist/Attack-on-Tank-5.1.0-luna17-r4.apk
```

上面的底层命令只构建修改菜单。加入 T‑54 应使用构建器，使资源适配、验证和签名顺序完整执行：

```bash
python -m pip install -r requirements-builder.txt
python -m tankbuilder build original.apks --config builder.config.json --tankpack T54_1949.tankpack --output dist/Attack-on-Tank-T54-r4.apk
```

`app/stubs` 只用于编译；打包时不会加入假的 Unity Activity。游戏库、元数据和资源必须匹配对应 profile；新版本不会因为名称相同而自动放行。

## 验证

```bash
python -m pip install -r requirements-dev.txt
python tests/test_native.py --module build/libaotmod.so --game-library /path/to/original/libil2cpp.so --report build/native-tests.json
python scripts/verify.py --apk dist/Attack-on-Tank-T54-r4.apk --apks /path/to/original.apks --unity-data build/T54-assets/data.unity3d --native-test-report build/native-tests.json
java -jar /path/to/apksigner.jar verify --verbose dist/Attack-on-Tank-T54-r4.apk
```

原生测试执行实际编译后的 ARM64 指令，覆盖玩家/敌方伤害区分、参数保留、原游戏 ObscuredInt 转换函数与数组边界、ADRP 重定位，以及换坦克的位置、朝向、玩家和镜头引用更新。换车验证直接执行原游戏 `_GenerateUnit` 和字符串比较指令，复现错误类型参数被拒绝，并检查六国玩家车型选择。组件查询按原始预制体层级设置边界：根对象可取得 `PlayerControl`，无法取得子对象的 `UnitStatus`。同一回归用例在 r2 编译模块上失败、在 r3 上通过；另验证空引用或已销毁的控制器/状态不会覆盖原玩家、镜头和车型配置。Unity 实例化及场景行为仍需设备实测。当前交付包的校验记录见 `verification.json`。

构建器测试：`PYTHONPATH=. python tests/test_builder.py --apks /path/to/original.apks`。测试涵盖新版/被修改二进制/资源变化拦截、默认关闭的草案、非法 Tank Pack 路径、无效参数和失败时保留已有输出。
