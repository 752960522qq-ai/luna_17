# 当前交付版本：坦无敌3000 / TankInvincible r9

游戏 5.1.0，ARM64，单人/本地对局。最新交付版本修正 T‑54 履带、机枪与后部散热网等 10 个金属材质。r8 涂漆调亮、r7 旧车退场与悬挂修复、120/240 mm 正面装甲、启动/菜单关注提示保留。尚未进行安卓真机测试。

## 仓库中的当前内容

- `prebuilt/5.1.0/r9/libaotmod.so`：从已验证 r9 APK 提取的原生模块，与通过 17 项回归的 r7 模块相同。
- `prebuilt/5.1.0/r9/mod.dex`：r9 APK 原始菜单 DEX，包含当前名称、版本和提示。
- `prebuilt/5.1.0/r9/snapshot.json`：APK、模块、菜单、资源与签名指纹。
- `tanks/T54_1949/`：实际 r8 调亮模型、纹理、绑定和当前玩家参数。模型以 42 个分块和指纹清单保存，材质脚本首次运行自动还原；也可执行 `python scripts/restore_t54_model.py`。还原 GLB 与原文件逐字节相同。r9 改动发生在 Unity 材质层，模型几何与图像 RGB 保持 r8 值。
- `scripts/repair_t54_metal_materials.py`：校验 r8 基线，重建金属材质，要求输出资源哈希与已交付 r9 完全一致。
- `scripts/package_t54_r9.py`：使用 r8 基线 APK、验证过的 r9 资源、仓库的当前 DEX/模块打包；支持只生成未签名包以及对齐、签名、验证。
- `reports/r9/` 与 r7/r8/r9 报告：资源检查、原生模块历史测试、APK 校验和修复范围。

## 源码恢复状态

此前尚未推送的工作区被自动维护清理。当前能恢复的是交付 APK、资源和验证记录；**r7 原生改动的完整源码没有恢复，`native/` 与 `app/src/` 保留远程构建器 2.0 源码（继承 r6 基线），不能称为 r9 的完整源码**。当前版本使用已交付 APK 的固定模块和 DEX，避免把较旧源码重编后覆盖修复。

`scripts/build.py`、GUI 和资源导入器沿用远程构建器 2.0 流程，使用 NDK 从源码编译；当前 r9 模块存放在独立 r9 子目录，仅供下述快照流程使用。重建当前 r9 应使用下述快照流程；完整源码模式需先补齐 r7 原生改动及 r8 导入器，再重新验证。

## 重建当前版本

准备已经交付的 `TankInvincible-5.1.0-T54-r8.apk`、`T54_1949-r8-resources.zip`。原版安装包、完整 Unity 数据、安装 APK 和签名私钥均不写入 Git；完整资源保留在已交付的资源文件中。

安装 `requirements-snapshot.txt` 中的固定依赖（含 UnityPy 1.23.0、pygltflib 1.16.5）。解压 r8 资源包后执行：

```bash
PYTHONPATH=. python scripts/repair_t54_metal_materials.py \
  --source input/r8/prepared-assets/data.unity3d \
  --model tanks/T54_1949/model.glb \
  --output-dir build/r9-assets

PYTHONPATH=. python scripts/package_t54_r9.py \
  --baseline input/TankInvincible-5.1.0-T54-r8.apk \
  --unity-data build/r9-assets/data.unity3d \
  --config builder.config.json \
  --output dist/TankInvincible-5.1.0-T54-r9.apk
```

配置中的 `zipalign`、`apksigner`、`keystore`、`password_file`、`alias` 使用本机工具和原开发签名。签名与对齐的顺序为修改资源、zipalign、签名、验证。仅检查包内容时可省略配置并指定 `--unsigned-only`，输出不能安装。

本次恢复后的材质脚本应重新产生 `f950c94a5445ff84c501875181e674e214ae595f747fe7ff3dd6289bd11b0646` 资源；不会对未知游戏版本直接套用。
