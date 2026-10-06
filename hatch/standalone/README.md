# Hatch · 舱盖 0.1 独立接入包

修改器名称为 **坦无敌3000**；Hatch / 舱盖是其坦克模组加载器名称。

这是可以重复接入《突击坦克 / Attack on Tank》5.1.0 ARM64 原版包体的加载器文件夹。无需重新编译加载器；使用 Python 3.10+ 和 JDK 17+ 运行一次接入脚本，脚本自动放置 DEX/原生库、修改启动入口、内置模组目录、对齐和签名。

**实验版：已验证编译、真实包体接入、签名及文件导入逻辑；尚未安卓真机验证 Unity 模型显示、操控和开火。** 本包原生核心基于 luna_17 最新源码分支 fix/r10-t54-controls（48eea65），集成 Hatch 0.1 加载器。原游戏资源及已有 .hatch 坦克包保持不变。

## 文件夹内容

- `loader/hatch.dex`：游戏启动入口、菜单、导入与扫描、内置模组释放逻辑。
- `loader/libaotmod.so`：ARM64 模型、贴图、参数加载与原游戏控制器接入。
- `adapters/attack-on-tank-5.1.0.json`：固定游戏版本指纹与适配资料。
- `mods/`：内置坦克包，已放入 T54_1949 示例；可删除示例或加入其他规范 `.hatch`。
- `module.json`：加载器版本及预编译文件校验值。
- `integrate.py`：自动接入脚本。只用 Python 标准库，签名工具已包含。
- `tools/apksigner.jar` 和 SDK NOTICE：Google Android 签名工具与附带许可通知。
- `tests/` 和 `verification/`：测试及验证记录。

## 一次接入

解压 ZIP，保留完整 `Hatch` 文件夹。安装 Python 3.10+ 与 **JDK** 17+（必须包含 java、keytool，加入 PATH）。在该目录执行：

```bash
python integrate.py --input "/path/Attack on Tank _ Rush_5.1.0.apks" --output "/path/Attack-on-Tank-Hatch.apk"
```

也支持已合并 ARM64 库的干净 5.1.0 APK：

```bash
python integrate.py --input "/path/original.apk" --output "/path/Attack-on-Tank-Hatch.apk"
```

脚本校验原游戏元数据、ARM64 库及配置中可用的资源指纹，拒绝未知版本和已接入修改器的输入。输入文件不会被覆盖。必须使用完整包，单独的 base.apk 缺少 ARM64 split 时不能接入。

默认在输出目录的 `Hatch-signing/` 创建一次本地开发签名，后续重建会复用。请保留自己的这个目录。它不包含在本独立接入包中。需要自己的签名时：

```bash
python integrate.py --input game.apks --output game-hatch.apk \
  --keystore /path/your.jks --password-file /path/password.txt --alias your_alias
```

只生成未签名包可以加 `--unsigned`，此时只需要 Python；未签名包不能安装。

输出旁边还有 `.report.json`，记录摘要、内置坦克和验证范围。新开发签名不能覆盖不同证书的原版/修改版。

## 放入游戏包体后的实际位置

接入脚本将界面 DEX 放在包根目录的下一个 `classesN.dex`，原生库放在 `lib/arm64-v8a/`，内置模组放在 `assets/Hatch/mods/`，目录清单放在 `assets/Hatch/catalog.json`。

**不能只把整个文件夹拖进原 APK 就直接运行；须执行接入脚本完成启动入口连接与重新签名。** 手动改 ZIP 而不接入入口，Android 不会主动执行里面的加载器。

## 首次启动与后续添加模组

本测试 APK 内置 T‑54，第一次启动会校验包内容并导入可写文件夹：

```
Android/data/com.LabenekoGames.Project_02/files/Hatch/mods/
```

点击左上角“坦无敌3000 → 舱盖 · 管理 / 导入坦克包”检查结果。进入单人对局，苏联列表中选择 `Hatch · T54_1949`，再点击替换当前坦克。

- 已有同 ID 的外置包会保留，不会被内置示例覆盖。
- 一个内置版本导入过后，用户删除外置包，重启不会再次自动恢复该版本。
- 以后添加新坦克，可通过游戏内菜单导入，或放入上述可写 `mods` 目录，完全退出并重启游戏；无需重编 APK。
- 若希望新的 APK 自带坦克，则把 `.hatch` 放入本独立包的 `mods/` 再运行脚本；这仍是重新打包和签名，但无需重新编译 DEX 或原生库。
- 游戏包体中的 `assets` 为只读内容，安装后不能直接向其中写入新模组。

## 支持范围

坦克包必须是 Hatch 0.1 格式。它包含原始 GLB、嵌入 PNG/JPEG、JSON 参数/rig 与已转换的 runtime.bin。原始 `.tankpack` 或散装模型需要先用现有 Hatch 转换器处理；任意 GLB 不会自动生成炮塔、炮管及轮组绑定。

最多 16 个坦克包、单包 256 MiB、总运行时缓冲区 512 MiB。模型创建还会额外占用 Unity/GPU 内存。仅单人对局；版本更新须重新校验适配器。

当前模型路径为静态网格与节点动画，暂未实现 GLB 骨骼蒙皮、履带骨骼变形、自定义 shader、外置音效或脚本模组。材质与实际操控仍需真机确认。

本次重新验证：19 项 ARM64 原生回归，34 个实际 Unity 接口及对应原生入口，36 张真实 PNG 的原始 ARM64 字节数组桥接与解码，完整生产加载流程（178 个节点、80 个网格），9 项接入测试及 5 项 Java 内置包释放检查。宿主加载流程使用模拟 Unity 对象；PNG 解码使用 Pillow；都不等同于 Android 图形驱动或 Unity 场景验证。

本次修复了 LoadImage 的字节数组/ReadOnlySpan 参数重载错误，删除游戏中已被裁剪的 Mesh.set_indexFormat 调用，并保留原始异常与出错贴图编号。模型单网格上限为 65535 顶点，大模型需先拆分网格。原有 0.1 坦克包无需重新转换；HE/HEAT 槽位在加载时适配游戏实际枚举。

源码仓库中的接入目录保存文本文件。预编译 DEX/SO 在 prebuilt/5.1.0/hatch-r10；完整独立 ZIP 包另附签名工具、模板模组及校验清单。直接运行 integrate.py 前须恢复 ZIP 中的完整布局，不能把仓库文本目录当作已发布 ZIP。
