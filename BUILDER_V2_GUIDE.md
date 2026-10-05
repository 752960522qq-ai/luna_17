# TankInvincible_3000 2.0：可复用坦克项目

适用原版 Attack on Tank 5.1.0 ARM64。支持新增可驾驶玩家坦克并通过局内 MOD 菜单选择；不向原选车商店添加条目，不修改 AI 目录。每次从原安装包构建，可合并最多 16 个独立坦克包。

## 桌面使用

启动 `Start-Builder.bat` 或 `python -m tankbuilder gui`。在“坦克 / 模型 / 贴图”页创建或打开项目，编辑参数，导入 GLB，按材质名替换贴图，保存检查并导出 `.tankpack`。在“APK 构建”页选择原安装包、配置和坦克包（可多选），构建 APK。

源码下载不包含用户模型和游戏资源。初次创建时使用 T54 参数和绑定示例；需要导入你自己的模型。也可直接打开已有完整项目。模板数值仅为初始值，不代表新车型的游戏实测数据。

## 命令行

```bash
python -m tankbuilder project create projects/MyTank --id MY_TANK
python -m tankbuilder project model projects/MyTank /path/to/model.glb
python -m tankbuilder project texture projects/MyTank /path/to/paint.png --material body_material
python -m tankbuilder project check projects/MyTank
python -m tankbuilder project pack projects/MyTank --output packs/MY_TANK.tankpack
python -m tankbuilder build original.apks --config builder.config.json --tankpack packs/MY_TANK.tankpack packs/OTHER.tankpack --output dist/MyTanks.apk
```

项目目录保存 `manifest.json`（ID/名称/国家）、`tank.json`（动力/航速/乘员/俯仰）、`weapon.json`（装填/初速/穿深/弹药）、`armor.json`（分区装甲）、`rig.json`（节点/炮口/碰撞体/悬挂）、`model.glb` 和 `thumbnail.png`。数值变化通过构建器生成原生配置头文件，不再逐车型修改 C 代码。

## 模型与贴图规范

- 米制、Y 向上、机头/炮口朝 -Z；炮塔绕 Y、火炮绕 X。
- 控制层级：`Hull` → `Turret` → `Gun` → `Barrel_Recoil`；转动节点初始旋转归零、缩放为 1。模型矩阵请转成 TRS；采用标准、未压缩、贴图内嵌的 GLB。
- 标准命名 `wheel_l_01…` / `wheel_r_01…`、`track_l…` / `track_r…`、`Muzzle_Main` 可自动生成基础绑定。自动推断的碰撞体是按尺寸生成的初值，导入后须检查。特殊命名使用 `--bindings bindings.json` 映射控制节点，并提供模型旁的 `rig.json`。
- 4–24 个负重轮，左右数量相同；轮组总数最多 28。特殊底盘、多个炮塔、无炮塔车辆需要其他控制适配器。
- 颜色与法线贴图可以按材质名替换。采用游戏已有移动材质着色器，避免依赖包内未编译的金属材质变体；不保证完整复现 GLB 的所有 PBR 特效。
- 添加的坦克共享 T34/85 的控制组件、弹道/音效和辅助装备模板。上述参数可定制；尚未暴露的模板行为保留。支持六个现有国家，不创建新国家。

## 构建依赖与缓存

Python 3.10+、JDK 17+、Android SDK、NDK。新增坦克或修改其参数必须配置 `ndk`；旧预编译模块不能替代新参数对应的模块。签名配置沿用 `BUILDER_GUIDE.md`，私钥不上传网页。

`asset_cache` 可指定资源缓存目录，默认配置文件旁 `build/asset-cache`。原资源、模型、参数、绑定或转换代码变化会生成新缓存键；命中时仍核对输出资源摘要。报告同时记录原生配置摘要和新增坦克目录位置。无需 AI 再次读取大模型，重复工作由固定程序完成。

网页支持项目配置、导入 GLB/Tank Pack、按材质替换贴图、浏览器本地保存和导出；实际签名 APK 由桌面/命令行构建器生成。

## 验证范围

本次用真实原始游戏资源验证 T54 模板与第二个德国目录测试坦克的同时注入，核对原对象保留、12 个战斗目录、网格、材质和引用；用 ARM64 指令模拟器验证配置参数及基础修改逻辑。测试用 ARM64 模块由通用交叉编译器构建，仅用于执行回归，不作为 Android 发布模块。

未进行安卓真机测试；没有为此版本生成签名 APK。新模型必须经过自己的模型检查、资源检查和设备运行测试。
