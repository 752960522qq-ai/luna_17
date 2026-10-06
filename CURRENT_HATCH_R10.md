# 坦无敌3000 / 舱盖 0.1：r10 加载修复

基于最新 fix/r10-t54-controls 提交 48eea65d70cf41e0640f467cd8a3b11f8b7d506d，集成 hatch-0.1 提交 9044e130aae50a25cf37a11183e6ae0dc91d412a 的数据加载器和菜单。修改器为坦无敌3000；加载器为 Hatch / 舱盖，版本仍为 0.1。

## 改动

- Unity 6000.3 的三参数 LoadImage 接收 ReadOnlySpan<byte>。旧实现传入 byte[]，导致错误长度及 Texture decode failed。改为实际保留的 LoadImage(Texture2D, byte[]) 两参数包装器；原生入口为 0x345f4f4。
- 游戏裁剪了 Mesh.set_indexFormat。移除该调用，使用默认 UInt16 索引；解析阶段拒绝单网格超过 65535 顶点，并要求拆分。T54 最大单网格 11710 顶点。
- 保留上游 Unity 异常；解码返回 false 时标明贴图索引和字节数。
- root BoxCollider 支持不同托管包装器指向同一个 Unity 原生对象。
- 兼容旧 Hatch 0.1 文件中的 HEAT/HE 顺序，加载时转换为游戏实际枚举 AP/HE/APCR/WP/HEAT。
- 动态外置坦克接入 r10 原生控制、炮镜和履带代码；继续使用原游戏 T34_85_Player 模板。此 APK 不包含 r10 静态资源注入方案，不声称已有 .hatch 模型已完成 r10 静态附件拆分或新增 HE 弹体池。
- 固定菜单名称及按钮留白，避免“坦无敌3000”文字被默认内边距挤掉。

## 验证

Android NDK r27d 编译 ARM64 模块；ECJ + Android 35 SDK + D8 编译菜单。19 项 ARM64 原生回归、34 个实际 Unity API 及原生入口检查、36 个原始 ARM64 贴图包装器/真实 PNG 解码检查、4 个完整生产加载流程与失败路径检查、9 项独立接入检查、5 项真实 Java 内置包释放检查通过。

贴图桥接执行游戏原指令，内部解码端用 Pillow 替代；完整加载流程通过 ASan/UBSan 执行生产 C 代码，Unity 对象及场景调用为模拟边界。所有这些都是离线证据。没有可用 Android 设备，尚未验证 Unity 图形驱动、实机安装启动、模型显示、驾驶、开火和连续换车，不能保证实机无问题。

T54_1949.hatch 与之前交付的独立模组完全一致，修复位于加载器，不要求重新制作模组。集成器和更新预编译模块位于 hatch/standalone/ 与 prebuilt/5.1.0/hatch-r10/。
