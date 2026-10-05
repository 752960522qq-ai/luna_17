T‑54 (1949) 当前模型来源：r8 调亮资源

模型分块为 `model.glb.part000` 至 `model.glb.part041`，清单为 `model.glb.parts.json`。执行 `python scripts/restore_t54_model.py` 可还原 `model.glb`；r9 材质脚本在文件缺失时自动还原，并核对完整 SHA‑256。

涂漆亮度参考原版苏联坦克校准，保留原磨损。r9 在 Unity 材质层进一步修正履带、机枪和散热部件；模型几何、贴图 RGB 与参数保持本目录值。当前重建使用仓库 CURRENT_R9.md 的快照流程，构建器 2.0 源码流程与 r9 快照流程分别验证，不能视为同一 APK。`rig.json` 保留 2.0 所需的碰撞体和悬挂配置；`rig-r8-snapshot.json` 保存交付 r8 的原始绑定。

玩家参数、骨骼、动画、悬挂、120/240 mm 前装甲及 r7 设置保持原值。r9 APK 已交付；资源和包检查通过，未进行安卓真机测试。
