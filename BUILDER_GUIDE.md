# 坦无敌3000 / TankInvincible 使用与版本更新

这是可运行的本地构建器和同名 ChatGPT 插件。插件负责检查与准备构建计划；大包处理、原生编译和私钥签名在本地或 ChatGPT 工作环境执行，插件服务器不保存 APK 或私钥。

## 初次使用

需要 Python 3.10+（建议 3.12）、JDK 17+。Windows 的 Python 官方安装包含桌面界面所需的 Tkinter；Linux 可安装系统的 Tk 包，或直接使用命令行。

1. 解压构建器，安装依赖：`python -m pip install -r requirements-builder.txt`。
2. 有 Android SDK 时，复制 `builder.config.example.json` 为 `builder.config.json` 并填写路径。没有 SDK 工具时运行 `python scripts/setup_builder_tools.py`；它从 Google 下载 API 35 和 Build Tools 35.0.0，校验大小与官方索引中的摘要，生成配置。SDK 的许可证保留在下载目录中。
3. 配置原测试版签名密钥及密码文件。密码只通过文件传给 apksigner，不写入构建器配置、报告或插件。构建器包和仓库均不包含你的密钥。原密钥备份由此前工作保留；在 ChatGPT 中继续构建时可复用。
4. 双击 `Start-Builder.bat`，或运行 `python -m tankbuilder gui`。选择原始 APK/APKS、配置文件和输出路径。
5. 点击“检测兼容性”，通过后点击“构建 APK”。输出目录有 APK、检测报告、构建报告及工具日志。

当前包附带 5.1.0 r5 原生模块。仅在模块及原生配置 SHA-256、游戏库、元数据、资源、20 项方法指纹及两项编码方法指针绑定均匹配时复用。byte/float 编码回归执行真实游戏指令。新版需要重新适配并编译模块；不能复用旧模块的哈希绕过适配。

```bash
python -m tankbuilder inspect "original.apks" --out build/inspection
python -m tankbuilder build "original.apks" --config builder.config.json --output dist/Attack-on-Tank-mod.apk
python -m tankbuilder build "original.apk" --config builder.config.json --features godmode infinite_ammo --output dist/Attack-on-Tank-two-features.apk
```

APK Set 的处理不是任意 split 的简单拼接。当前包型可直接合并；遇到多个 ARM64 候选或独立资源 split 时会阻止构建，需要 bundletool 选择正确设备安装集或另写资源合并适配器。

## 官方版本更新后的流程

1. 保留原游戏安装包和已有 Tank Pack，检测新版：`python -m tankbuilder inspect new.apks --out build/new-version`。
2. 生成草案：`python -m tankbuilder draft-profile new.apks --out profiles/attack-on-tank-NEW.draft.json`。草案默认 `verified=false`，所有修改功能默认关闭；携带新版版本号、Unity 版本和资源摘要。
3. 分析新版元数据，重新核对函数签名、参数类型、RVA、字段布局、API 导出名、字符串标签及预制体层级。旧 RVA 处恰好有相同指令、类名仍存在，都不构成完整兼容证据。
4. 更新 `native_macros`、`fields`、`hooks`、`api_symbols` 和 `fingerprints`。尚未提取成宏的游戏字段、IL2CPP ABI、元数据解码和回归程序也必须随版本核查；必要时修改对应适配代码。第一版不自动反编译或重新定位所有符号。
5. 在配置中移除 `native_prebuilt`、设置 `ndk` 路径。编译新模块，更新该版本对应的 ARM64 回归，测试换车的位置/朝向/镜头和失败保留路径。记录真实结果后审核配置，才设置 `builder.verified=true` 和已验证功能。
6. 真机测试启动、换车、移动、瞄准、开火、结束对局和联机暂停。报告分别记录程序回归与真机结果，不能互相代替。
7. 使用同一签名重建，核对证书和输出哈希；新增更新日志，再更新同一插件和配置。

## Tank Pack

`.tankpack` 是 ZIP，根目录包含 `manifest.json`、`tank.json`、`weapon.json`、`armor.json`、`model.glb`、`thumbnail.png`。参数采用中立单位（速度 km/h、发动机功率 hp、时间 s、角度 °），格式中记录 `units`；它们需要版本适配器映射到游戏真实字段，不能直接当作游戏内部值。

```json
{"format":1,"id":"T72A","displayName":"T-72A","country":"USSR","tier":5,"basePrefab":"T34_85_Player","units":{"speed":"km/h","power":"hp","time":"s","angle":"deg"}}
```

`tank.json` 的必需项为 maxForwardSpeed、maxReverseSpeed、enginePower、crew、gunElevation、gunDepression、turretRotation；`weapon.json` 需要 caliber、reload、ammo；`armor.json` 保存分区装甲参数。模板见 `tanks/template`，参数为格式示例，未声称是游戏实测数据。

```bash
python -m tankbuilder tankpack T72A.tankpack
```

1.1.2-dev 支持已审核的 `T54_1949.tankpack`，额外包含 `rig.json`。其他 Tank Pack 仍只校验格式，没有通用模型注入能力。当前适配器将模型转换为 Unity 网格/材质，克隆玩家预制体，连接炮塔、火炮、发射点和碰撞体，并向 12 个战斗场景的玩家目录追加 T‑54；保持 AI 数组和原选车界面的全部原始对象。T‑54 通过战斗中的 MOD 菜单选择。

r6 使用固定的 `unity-6000.3.19f1.json.gz` 完整 release 类型树，来源和哈希保存在文件内。每次写入要求原对象完整消费、未修改树逐字节往返一致；保存后另核对继承渲染器、完整网格/LOD/骨骼和资源引用。更新 Unity 版本时必须重新核验对应类型树，不能把旧前缀与假定的尾部拼接后直接放行。

只准备资源而不生成 APK：

```bash
python -m tankbuilder prepare-assets original.apks --tankpack T54_1949.tankpack --out build/T54-assets
```

生成带 T‑54 的 APK：

```bash
python -m tankbuilder build original.apks --config builder.config.json --tankpack T54_1949.tankpack --output dist/Attack-on-Tank-T54-r5.apk
```

资源适配器还会严格核对原始 data.unity3d 指纹。更新游戏版本后需重新核对序列化字段、模板 ID、玩家目录和原生控制器；不能把上一版派生资源直接放进新版 APK。

## 插件使用

插件名为 **TankInvincible_3000**。连接后可询问“读取当前支持版本”“检查这份 inspection.json”“为这个安装包准备修改器构建计划”“读取更新日志”。安装包可在私人页面中直接读取检测，文件内容在浏览器处理，只发送小型检测 JSON；也可导入本地生成的 inspection.json。

准备计划不会直接返回 APK。ChatGPT 或本地构建器必须读取真实输入包、复核指纹并执行构建。插件不拥有私钥，也不在 Worker 中运行 Android 编译工具。

参考：[apksigner](https://developer.android.com/tools/apksigner)、[zipalign](https://developer.android.com/tools/zipalign)、[bundletool](https://developer.android.com/tools/bundletool)、[UnityPy](https://github.com/K0lb3/UnityPy)。
