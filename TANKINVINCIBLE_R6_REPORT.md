# 坦无敌3000 / TankInvincible r6 修复记录

本次针对“原选车界面能进入，但任意阵营载具加载战斗场景都会闪退”的报告，修复已复现的 Unity 资源字段错位与截断，并重新生成、签名 APK。修改器中文名为“坦无敌3000”，英文名为“TankInvincible”。尚无安卓设备运行日志，不能把静态资源通过等同于真机不再闪退。

## 缺陷与修复

UnityPy 1.23.0 内置的旧 Renderer 布局不包含 `m_ForceMeshLod`、`m_MeshLodSelectionBias` 和新掩码位置；旧 Mesh 布局也缺少 `m_MeshLodInfo`。这些差异既包含中间插入字段，也包含新增末尾字段。仅在旧树后追加字节，不能修复字段错位。

r5 写入器还把 Boost 外层 reader 的位置当成实际消费位置。Boost 先读取整个对象，其实际解析长度另行返回；因此“剩余尾部”被错误计算为空。已交付 r5 的 174 个继承渲染器确实被截断。新检查在 r5 的 MeshRenderer/ParticleSystemRenderer 样本上返回 `read_int out of bounds` 并拒绝产物。

r6 固定使用与游戏版本一致的完整 release 类型树。写入前后必须完整消费对象，并把未修改树写回后逐字节比较；不匹配时停止。原生组件的引用按准确字段重映射。新增网格生成一层、与自身索引缓冲一致的 LOD 数据；新渲染器清理源静态批处理、探针和附加顶点流绑定。MonoBehaviour 仍使用已登记的游戏字段编码器。

类型树来源：[AssetRipper TypeTreeDumps / 6000.3.19f1](https://github.com/AssetRipper/TypeTreeDumps/blob/70942d203f7a9899ac15375b66058dbbfab31efd/InfoJson/6000.3.19f1.json)。完整原 JSON SHA-256：`3aaf47994972c7c4f6dcd596a45be5e3dc640a790f123b0529ad64ed0df8a265`。工程保存 17 类所需结构的压缩快照，SHA-256：`abb1c149faa5cd7d4c08de7207a05d0430165b320dfad672775d4b9e54748dfc`。

## 实际检查结果

| 检查 | 结果 |
|---|---|
| 原预制体 797 个原生组件 | 完整解析，未修改树逐字节往返一致 |
| 174 个继承渲染器 | 与准确重映射后的原件逐字节一致；截断数 0 |
| 1,283 个新增原生对象 | 保存后完整解析与往返一致 |
| 3,010 个原生资源引用 | 已解析到包内对象 |
| 14 个 Unity 内置引用 | 与原模板的类、外部资源名和对象 ID 对应，未新增未知引用 |
| 80 个新网格、两条履带 | 索引范围、LOD、材质引用和 11 根履带骨骼检查通过 |
| 原选车及菜单场景 | 每个原对象保持原始字节 |
| 12 个战斗目录 | 仅苏联玩家数组追加 T‑54；其他阵营与 AI 数组不变 |
| 原资源对象及 612 个 APK 条目 | 字节保持原始内容 |
| 构建器回归 | 11 项通过 |
| 实际 APK 模块的 ARM64 回归 | 11 项通过，包括真实 byte/float 编码 |
| 名称 | 安卓应用/启动活动为“坦无敌3000 · TankInvincible”；菜单分别显示中文名与英文名 |
| 签名及对齐 | zipalign 与 apksigner verify 通过；证书与此前修改版一致 |
| 安卓真机 | 未执行 |

## 输出

- APK：`TankInvincible-5.1.0-T54-r6.apk`
- 大小：198,131,625 字节（188.95 MiB）。
- APK SHA-256：`b3acc95cb676f88f338cb7abc689bbd079e752e54cd1c7ba0c60d10d05ed42a0`。
- 派生 Unity 资源 SHA-256：`0b60bddfbf2291d1050be7f94a9bc0e730559fdf9682559798cb16f10e6b678b`。
- 签名证书 SHA-256：`9b09d75b77a30e67aa14196823b41cc04c70cb3ec6ac1eab41c41f0980568571`。
- 原生模块沿用 r5 的同一模块；本次修复针对资源和名称。

可覆盖更新此前相同开发签名的修改版。进入战斗后，从 MOD 菜单选择“苏联 → T54_1949_Player → 替换当前坦克”。

修复的是已证实的资源结构缺陷；尚需设备确认任意阵营战斗入场、T‑54 换车与射击。自动验证不包含 Unity 引擎在手机上的实际加载，也没有新增篡改提示处理路径。完整结果见 `verification.json`、`builder-verification.json` 和 `CHANGELOG.md`。
