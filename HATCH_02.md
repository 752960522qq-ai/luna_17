## 原生库加载修复（已打包）

启动门仍先完成前置初始化，再启动 Unity。原生库现在由加载器中的 `NativeHost` 固定持有，与游戏引擎共享应用原生命名空间；前置模块自己的 JNI 方法通过 `RegisterNatives` 绑定，模块类加载器不再调用 `System.load`。

`ModuleSession` 保存模块实例、类加载器及首次启动结果。初始化失败后保留第一次错误，不重新解包或创建另一套类加载器。前置区分库已加载与钩子已就绪；错误信息包含 IL2CPP 查找、游戏入口指纹、缺少 API、钩子安装及回滚阶段。

本次验证通过：32 项 ARM64 执行测试、5 项 JVM 启动门测试、5 项真实 JVM/JNI 模块加载测试。双子类加载器测试实际加载主机原生测试库，并复用生产 JNI 注册表及 Java 桥；游戏操作由测试实现代替，不是 Android/Unity 实机测试。

签名沿用舱盖 0.2 的签名，已重新编译并内置坦无敌3000 1.0。既有坦克包格式保持兼容，T54 与玛蒂尔达的模型数据不变。仍未连接安卓设备，Android 链接器及选关场景实跑待验证。构建新加载器时必须一起重新编译前置，不能混用仓库旧的预编译前置。

# 舱盖 Hatch 0.2 / 坦无敌3000 1.0

舱盖负责文件导入、校验、依赖检查和模块启动。坦无敌3000 是必备前置 `.hatch`，包含菜单、游戏适配、换坦克、模型绑定、武器、弹道和弹匣逻辑。APK 的新增 DEX 只包含 `com.hatch.loader`；不再直接内置修改器 DEX 或 `libaotmod.so`。首次启动将前置包和内置坦克包释放到游戏外部文件目录的 `Hatch/mods`。

## 目录与职责

| 路径 | 职责 |
| --- | --- |
| `loader/src/com/hatch/loader` | 通用包校验、导入、依赖、动态加载和公开接口 |
| `mods/tankinvincible/src` | 坦无敌3000 1.0 菜单与接口实现 |
| `native/aotmod.c` | 原生初始化与钩子注册 |
| `native/runtime_support.h`, `ammo_runtime.h`, `tank_catalog.h`, `tank_swap.h` | Unity 调用、弹药、目录、换车事务 |
| `native/imported_tanks.h`, `ballistics_runtime.h`, `magazine_runtime.h`, `view_runtime.h` | 弹道、弹匣、视角 |
| `native/hatch_data.h`, `hatch_engine.h` | 运行数据解析与模型资源绑定 |
| `hatch/package.py`, `hatch/pack.py` | 前置包校验/打包、坦克包编译 |
| `scripts/build.py`, `scripts/repack_hatch.py` | 分别编译加载器和前置，组装并签名 APK |

`scripts/repack.py` 仅保留二进制 XML 和 ZIP 工具；当前构建统一从 `scripts/build.py` 进入。旧 `app/src` 内嵌修改器入口已移除，`app/stubs` 只用于编译，不进入 APK。

## 使用

安装 APK 后，第一次启动会自动安装坦无敌3000 1.0、T54 和玛蒂尔达。菜单中的“舱盖 0.2 · 管理 / 导入模组”可以导入 `.hatch`，也可以将文件放入游戏外部文件目录的 `Hatch/mods`。导入、更新或删除后需要完全退出进程再启动。缺少前置时会提示错误并提供导入按钮；不会启用修改功能或加载坦克。读取旧 Hatch 0.1 坦克包时隐含依赖坦无敌3000 1.0。

模块清单采用 format 2、type `module`、API 2，载荷为 `module.dex` 和 `module.so`，均带 SHA-256 和字节数。坦克清单采用 format 2、type `tank`，声明 `requires: {"tankinvincible3000":"1.0"}`。运行数据仍为 HATCH01，保留旧包兼容性。当前适配仅支持游戏 5.1.0 / ARM64。

## 弹匣炮坦克

在坦克项目 `weapon.json` 中加入以下配置，然后用 `hatch.pack` 编译：

```json
"magazine": {
  "capacity": 5,
  "shotInterval": 0.25,
  "reloadTime": 8.0
}
```

该示例表示每匣 5 发、匣内射击间隔 0.25 秒、最后一发后整匣装填 8 秒，是功能示例参数。不是二号坦克的历史参数，也不是完整二号坦克模型包。编译器会把配置写入 `hatch.json`。容量允许 2–200，射击间隔 0.03–60 秒，整匣装填时间不得小于间隔且不得超过 300 秒。

每次成功发射主炮才消耗匣内一发；同轴机枪、失败发射不计数。实际总备弹仍由游戏管理；无限弹药不会取消整匣换弹。暂停使用游戏时间，换车或新对局重置当前玩家弹匣。无 magazine 配置的坦克继续使用原来的单发装填。暂不提供主动丢弃残匣或逐发补弹。

```bash
PYTHONPATH=. python -m hatch.pack path/to/tank-project --output dist/NewTank.hatch
PYTHONPATH=. python scripts/prepare_hatch_weapons.py --source original/data.unity3d --output-dir build/hatch-assets
python scripts/build.py --apks original.apks --ndk /path/to/android-ndk \
  --android-jar /path/to/android.jar --r8 /path/to/d8.jar \
  --apksigner /path/to/apksigner.jar --zipalign /path/to/zipalign \
  --unity-data build/hatch-assets/data.unity3d \
  --hatch dist/NewTank.hatch --output dist/Attack-on-Tank-Hatch-0.2.apk
```

`original/data.unity3d` 从原始 APK 的 `assets/bin/Data/data.unity3d` 提取。干净游戏包必须配套上述武器模板；构建时缺少模板会明确拒绝，避免导入 HE 坦克后才失败。

构建输出同时包含 `TankInvincible3000-1.0.hatch`。支持干净 APK/APKS，另有经过 SHA-256 限定的 r11 发布 APK 迁移入口。游戏资源与签名私钥不提交到仓库。

## 本次修复与验证边界

炮镜使用当前车辆的仰俯角和实际炮管世界姿态，原版车辆也适用；切换飞机视角/目标时清理旧的准星垂直校准。模组主炮保留原弹种速度倍率，在实际 ShellMove 初始化时补偿原版的 0.23 速度缩放，并设定重力 9.81；原版弹道保持原样。T54 的 HE 池也保留 ShellMove 轨迹组件。玛蒂尔达 AP 穿深保持 89 mm。

25 项 ARM64 Unicorn 检查通过，其中实际执行原游戏炮弹初始化/重力指令；两款坦克用生产资源加载器通过 ASan/UBSan 主机检查，覆盖网格、贴图、模型控制层级、机枪与炮弹渲染器保留。另检查 39 个 Unity API、全部 58 张贴图、包校验、DEX 分离、ELF 依赖与对齐、APK 签名。

以上不是 Android 实机、Unity 场景或 GPU 测试。当前环境没有连接 Android 设备，不能据此保证设备上没有问题。正式给第三方使用前仍需要设备验证。
