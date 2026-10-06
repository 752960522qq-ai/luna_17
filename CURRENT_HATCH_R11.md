# Hatch 0.1 / 坦无敌3000 r11

此修订修复导入坦克的履带滚动、同轴机枪音源父节点以及炮弹网格隐藏问题。模板补齐两个完整 HE 炮弹池，T54 模组把混合细节拆分到车体和炮塔，并将天线挂到炮塔。Matilda III AP 穿深按用户要求设为 89 mm，其他参数保持一致。

修改器名为坦无敌3000，加载器名为 Hatch / 舱盖，加载器格式与版本仍为 0.1。升级已有安装时，使用游戏菜单重新导入两个更新后的 `.hatch`，完全退出并重启游戏。内置包不会覆盖用户已有模组。

## 代码

`native/hatch_api.h` 管理 Unity 接口与错误；`hatch_engine.h` 创建模型和贴图；`hatch_controls.h` 绑定碰撞体、轮组、炮塔和炮管；`hatch_weapons.h` 保留武器子树并迁移完整挂点；`track_material.h` 使用游戏保留的材质方法。

`tankbuilder/weapon_assets.py` 为静态构建器和 Hatch 模板共享炮弹池处理。静态构建器克隆模型时也保留武器子树，避免隐藏弹体。`scripts/prepare_hatch_weapons.py` 从原始 Unity 资源生成带 HE 池的模板，仅改原模板的 Launcher 和 Fire Point Transform 两个对象。`scripts/rebuild_hatch_mods.py` 从已有两个模组重新生成更新后的模型与数据。

## 构建

从原始 5.1.0 ARM64 APKS 提取 `assets/bin/Data/data.unity3d` 后，先准备模板，再使用 `scripts/build.py`：

```bash
PYTHONPATH=. python scripts/prepare_hatch_weapons.py --source original/data.unity3d --output-dir build/hatch-assets
PYTHONPATH=. python scripts/rebuild_hatch_mods.py --t54 T54_1949-Hatch-0.1.hatch --matilda Matilda_III-Hatch-0.1.hatch --output-dir build/mods
PYTHONPATH=. python scripts/build.py --apks game.apks \
  --native-prebuilt prebuilt/5.1.0/hatch-r11/libaotmod.so \
  --android-jar tools/android.jar --r8 tools/d8.jar \
  --apksigner tools/apksigner.jar --zipalign tools/zipalign \
  --unity-data build/hatch-assets/data.unity3d \
  --hatch build/mods/T54_1949-Hatch-0.1.hatch \
  --hatch build/mods/Matilda_III-Hatch-0.1.hatch \
  --keystore private/development.jks --password-file private/password.txt --alias hatch \
  --output dist/TankInvincible3000-Hatch-0.1-r11.apk
```

编译原生源码可将 `--native-prebuilt` 换为 `--ndk`。Java 编译器可以使用完整 JDK，或传入 `--ecj compiler.jar`。必须使用已有签名密钥才能覆盖同证书的已安装版本；密钥不在仓库中。

## 验证范围

19 项实际 ARM64 模块回归通过；39 个 Unity 接口及原生入口通过实际游戏元数据审计。履带测试执行新版模块与游戏原有 `SetTextureOffsetImpl`，在模拟材质边界验证前进、倒车和转向。Matilda 外置配置执行原生状态与攻击信息路径，确认穿深 89 mm、初速 853 m/s 和装填 2.8 s。

两辆坦克的生产加载代码通过 ASan/UBSan 模拟 Unity 测试，验证弹体与粒子保留、机枪父节点、轮组和履带绑定。原始贴图桥接执行游戏 ARM64 字节数组包装，内部解码用 Pillow。T54 180 节点/36 张贴图，Matilda 155 节点/22 张贴图；履带最低点和车体支持盒底均为模型 Y=0。

没有 Android 实机和真实 Unity/GPU 测试。离线验证不代表已确认实机的显示、音效、碰撞和复杂地形动作无问题。历史 r10 独立接入快照保持原样；r11 的 HE 修复需要上述模板准备步骤，不能只替换旧独立包的原生库。
