# T-28（1934 年式）

苏联 Tier II 中型坦克。用户提供的三炮塔模型带圆柱形主炮塔、环形天线及短身 KT-28，对应早期无附加装甲的外形。玩家车与 AI 分别注册，战役出场名单没有改动。

| 项目 | 游戏数据 |
| --- | --- |
| 乘员 / 重量 | 6 人 / 28 吨 |
| 发动机 / 公路速度 | M-17、450 马力 / 37 km/h |
| 模型长、宽、高 | 7.44 × 2.87 × 2.82 m |
| 正、侧、后（车体 / 主炮塔） | 30、20、20 mm / 20、20、20 mm |
| 主炮 / 总备弹 | 76.2 mm KT-28 / 70 发 |

等级、装填时间、两种炮弹的数量分配、倒车速度和伤害属于游戏调校。`T28` 是独立车库 ID；原生玩家、AI 及两份车辆简介分别挂在 `unit/so/t28/` 下。AI 使用原版 AIControl 和名称标识；玩家用原版瞄具及主炮、同轴 DT。两座前机枪塔各有回转轴、俯仰轴及枪口，随当前主炮塔方向在各自的前方扇区转动，不额外生成两个独立火控器。

保留原车体及轮组 UV、五组法线细节，绿色涂装和红星单独处理。每侧拆为十二个负重轮、四个托带轮、一个诱导轮和一个主动轮；游戏内左右履带分别滚动，原始节纹完整保留。GLB 的每侧接地段随十二个悬挂锚点变形。主炮管后坐时同轴 DT 和两座前炮塔不跟随后坐。

- 实车照片：[World War Photos 的 T-28 照片](https://www.worldwarphotos.info/gallery/ussr/tanks-2/t-28-tank/)。规格参考：[T-28 Model 1934](https://www.onwar.com/tanks/ussr/data/t28m34.htm)。
- 原模型：[T-28](https://sketchfab.com/3d-models/t-28-fa6c701018c043558a892ed6e3e8db8f) by [mamont nikita](https://sketchfab.com/mamontnikita62)，[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。改动包括苏联绿、红星、按米缩放、轮组/三炮塔绑定、骨骼及预览。署名、许可、来源和改动说明也在交付 GLB 和 Hatch 的 rig.json 中。

从源码更新（使用仓库原有环境和 5.1.0 版游戏的 Unity 资源）：

```sh
python -m tankbuilder.t28.build "$SOURCE_GLB" tanks/T28
python -m tankbuilder.t28.verify tanks/T28
blender -b -P scripts/render_bt7.py -- --project tanks/T28 --out "$RENDER_DIR" --motion
python scripts/panzer3f_preview.py "$RENDER_DIR" "$PREVIEW_DIR" --t28 --motion --thumbnail tanks/T28/thumbnail.png
python -m tankbuilder.panzer3f.integrate --apk "$BASE_APK" --index "$BASE_AI_INDEX" --project tanks/T28 --prior "$CORRECTED_PZ3F_STAGE" --companion "$ARM64_COMPANION" --out "$STAGE"
```

`ARM64_COMPANION` 用仓库 `scripts/build_campaign_runtime.py` 的 clang 参数编译 `campaign-runtime/campaign.c`。`--prior` 引用已经更新炮管的三号 F 的暂存目录。暂存目录只产生游戏资源，不生成 APK。

从已经交付的文件重建相同的完整覆盖层，不重新转换模型：

```sh
python -m tankbuilder.panzer3f.restore --apk "$BASE_APK" --integration T28-Integration.json --overlay T28-Resources.overlay --vehicle T28.hatch --additional-vehicle Panzer_III_Ausf_F.hatch --companion libhatchcampaign.so --out "$STAGE"
```

该步骤会在输出前验证基础游戏、两车的 Hatch 模组、ARM64 组件和组合后的 Unity 资源；不用先恢复单独的三号 F 覆盖层。
