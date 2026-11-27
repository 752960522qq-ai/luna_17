# 模组坦克的敌方 AI 预制体（Hatch 0.4 / Attack on Tank 5.1.0）

每辆车对应一个独立的 Unity `SerializedFile`（`*_AI.assets`）。文件里有一个可实例化的敌方 `GameObject` 根节点，另有一个 `TextAsset` 保存该车的原始模组配置。用 `Hatch-Enemy-AI-index.json` 里的 **文件名与 `root_path_id` 一起**识别根节点。不同文件可以有相同的 PathID。它们不是 Unity 编辑器 YAML、AssetBundle、`.hatch` 包或 Android 安装包。

| 敌方预制体 | 原游戏 AI 底车 | 初始弹种 | 左 / 右负重轮 |
| --- | --- | --- | --- |
| Grille_AI | Brummbar_AI | HE | 4 / 4 |
| Matilda_III_AI | Valentine_AI | AP | 10 / 10 |
| Panzer_II_Ausf_L_AI | Panzer_38t_AI | AP | 5 / 5 |
| SU_152_AI | ISU_122_AI | AP | 6 / 6 |
| T26_AI | T34_76_AI | AP | 8 / 8 |
| T30_AI | T29_AI | AP | 8 / 8 |
| T44_100_AI | T44_AI | AP | 5 / 5 |
| T54_1949_AI | T44_AI | AP | 5 / 5 |

## 生成和验证

安装仓库的 `requirements-builder.txt`。从仓库根目录执行：

```bash
python -m tankbuilder.enemy_prefabs \
  --apk /path/to/Hatch-0.4-Grille-HE200-T26.apk \
  --output /path/to/Hatch-Enemy-AI
```

构建器只读输入 APK，从各车型已发布的 `runtime.bin` 获取几何体、纹理和控制节点；从同一车型的 JSON 读取配置。它核对原游戏资源指纹、每辆车的运行数据 SHA-256、弹药和装药配置，然后输出 8 个独立资源及索引。无须 Android SDK、签名密钥或 Unity 编辑器。不会运行 APK 构建或修改场景目录。

每个文件写入后会用仓库的 Unity 6000.3.19f1 类型树重新解析，核对敌方身份、AI / 驾驶组件、炮塔与炮管层级、炮口与后坐、弹池归属、左右履带及悬挂。输出网格的顶点、三角形、UV、材质贴图引用以及贴图像素与运行模型逐项比较。碰撞排除引用跟随各自底车的原设计（车体或炮塔）。蟋蟀初始装 HE，配置为 **200 mm / 12,300 g**。T‑26 只有 AP，保留左右各 8 个负重轮和独立悬挂支点。

如需运行破坏性样本的回归检查（仅作用于临时副本），从输入 APK 读出原 `assets/bin/Data/data.unity3d`，运行：

```bash
PYTHONPATH=. python tests/test_enemy_prefabs.py \
  --data /path/to/data.unity3d --staged /path/to/Hatch-Enemy-AI
```

## 后续接入边界

这些文件需要与同版本的 `resources.assets`、`globalgamemanagers.assets`、相关 `sharedassets` 和 Unity 内置资源一起解析。`profile_path_id` 指向每车自己的配置：车体、装甲、弹药及装药、弹匣和悬挂等。预制体复用原游戏的 AI 决策、驾驶、武器、伤害和敌我识别组件。初始化时游戏可能按原版 `unitType` 再取数；后续接入应以模组 ID 读取该配置，不要把底车当作最终车型。

这一步不向关卡、玩家车库或联机预制体表注册车辆，也不改变刷怪概率。后续接入单人战斗时，应将各车型资源作为独立序列化文件引入，给相应战斗场景的敌方车型数组追加外部 `PPtr<GameObject>`（目标文件和 `root_path_id`），保留原始槽位，最后在游戏里实测寻敌、行驶、开火和受击。目前没有进行 Unity Play Mode 或 Android 真机实战测试。
