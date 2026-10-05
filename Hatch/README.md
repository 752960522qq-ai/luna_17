# Hatch · 舱盖 0.1

面向《Attack on Tank / Rush》5.1.0、Android ARM64 的外置坦克包加载器原型。

本项目是从构建器 2.0 / r6 可恢复源码创建的独立子工程，不替代仓库已有 r9 快照，不声称包含缺失的 r7 原生修复。

**状态：实验版。** 已完成 Android/ARM64 编译、包解析测试和原生切车回归；尚未在 Android 真机中验证 Unity 模型创建、贴图显示、操控与开火。不应将测试通过等同于已经在游戏里成功运行。

## 已实现

- 启动时扫描游戏自己的 `files/Hatch/mods/` 中的 `.hatch` 文件。
- 游戏浮窗提供“管理 / 导入坦克包”，通过系统文件选择器导入。
- 根据坦克 ID 去重，校验格式、兼容版本、内容 SHA-256、模型层级、网格索引、参数和贴图尺寸。
- 从运行时数据创建模型节点、Mesh、材质和 PNG/JPEG 贴图，接入炮塔、炮管、轮组、武器挂点和碰撞区域。
- 将外置坦克加入浮窗对应国家的车型列表；在单人对局中，以原游戏 T34_85_Player 为控制器模板生成新车。
- 接入装甲、弹药、穿深、口径、初速、装填、功率、速度、重量、炮塔转速、俯仰角等配置；使用原游戏的控制器与炮弹系统。
- 加载失败时取消切换，保留当前坦克。限单人模式。

## 使用测试版本

1. 安装 `Hatch-0.1-experimental.apk`。这是新开发证书签名的测试安装包，不能保证覆盖已有不同签名的安装。游戏 package 和游戏版本号仍保留原值；加载器版本为 0.1。
2. 点击游戏左上角“舱盖”，选择“管理 / 导入坦克包”，选择示例 `T54_1949-Hatch-0.1.hatch`。
3. **完全退出游戏进程并重启**，再次打开管理窗口检查“已加载”数量和每个包的结果。
4. 进入单人对局，在浮窗“对局换坦克”的苏联列表中选择 `Hatch · T54_1949`，点击替换。

也可以将文件直接放到：

```
Android/data/com.LabenekoGames.Project_02/files/Hatch/mods/
```

Android 对 `Android/data` 的文件管理权限因系统而异，因此提供了游戏内导入入口。删除模组文件、重启后即不再加载；更新同一个 ID 的文件也须重启。0.1 不提供对局热加载。

## 后续添加坦克

`.hatch` 是可放入游戏的坦克文件。一个包同时保留原始模型、贴图及 JSON 配置，并携带预解码的 `runtime.bin`，手机不需要 Python，也不需要重编 APK。

在电脑上，把现有审核通过的 `.tankpack` 转换一次：

```bash
python -m pip install -r requirements-hatch.txt
python -m hatch your_tank.tankpack --output your_tank.hatch
```

也可从完整坦克项目文件夹转换：

```bash
python -m hatch path/to/tank_project --output your_tank.hatch
```

完整项目包括 `manifest.json`、`tank.json`、`weapon.json`、`armor.json`、`rig.json`、`model.glb` 和 `thumbnail.png`。示例 `.hatch` 内包含这些原文件，可以解压取出作为起点。源码中的 `tanks/T54_1949/` 只保留配置，模型请从示例包取出。

`model.glb` 要求明确的 Hull / Turret / Gun / Barrel_Recoil 层级、轮组和履带节点，使用 TRS 变换、三角形网格及嵌入 PNG/JPEG。这不是对任意模型文件的自动适配器；新模型必须先完成对应 rig。旧 `.tankpack`、原始 GLB 和散装贴图须先转换，不会被手机直接识别。

## 0.1 的限制

- 仅适配 5.1.0 / ARM64；其他游戏或版本须另写适配器。
- 最多 16 辆外置坦克；单个 runtime.bin 最大 256 MiB，总运行时缓冲区最大 512 MiB。GPU/Unity 对象还会额外占用内存。
- 最多 2048 节点、128 张贴图；单网格 20 万顶点 / 60 万索引；贴图最大 4096 × 4096、16 MiB。
- 使用静态网格与节点动画。暂未实现 GLB 骨骼蒙皮、履带骨骼变形、GLB 动画片段、自定义 shader、外置音效或脚本模组。
- 标准色贴图和法线贴图可以创建；材质继承游戏模板，尚未保证全部 PBR 通道及法线解码效果。
- 爆炸、声音、控制器等复用原车型；实机物理与视觉匹配尚需验证。

## 复现构建

安装 JDK 17+、Android SDK platform 35 / build-tools 35、Android NDK r27d。构建参数与原 builder 保持一致，源码入口是 `scripts/build.py`。`--native-prebuilt` 可使用 `prebuilt/5.1.0/libaotmod.so`；修改原生代码后须用 `--ndk` 重编。

```bash
python scripts/build.py --apks /path/game.apks --ndk /path/android-ndk-r27d \
  --android-jar /path/android.jar --r8 /path/r8.jar \
  --apksigner /path/apksigner.jar --zipalign /path/zipalign \
  --alias hatch --output Hatch-0.1-experimental.apk
```

原游戏安装包和开发签名密钥不包含在源码中。构建脚本自动创建本地开发密钥；后续升级测试包须保留同一密钥。

## 验证范围

- 7 项原生包解析测试，通过 ASan / UBSan 检查实际示例模型与损坏输入。
- 12 项 ARM64 Unicorn 回归，执行原游戏构造器和载具工厂，覆盖配置、原车型切换、武器等待与 Hatch 创建失败回退。
- Java / DEX / ARM64 编译、签名、16 KiB ELF 对齐和安装包结构验证。
- 测试不覆盖真实 Unity 引擎运行。`verification/` 保存本次报告。
