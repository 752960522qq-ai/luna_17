# 二号 F 型轻型坦克（Panzer II Ausf.F）

玩家车 ID `Panzer_II_Ausf_F`；国家德国；Tier Ⅰ。支持 Attack on Tank 5.1.0 ARM64、Hatch 0.4 和「坦无敌3000」1.0。它有自己的玩家模组和敌方预制体，不覆盖二号 L 型「山猫」、BT-7 或额外战役。

## 驾驶与关卡使用

- 手机端在「模组管理 → 导入 .hatch」选择 `Panzer_II_Ausf_F.hatch`，完全退出并重新启动，在模组坦克中选 `Panzer II Ausf.F`。
- 玩家版按住主炮键连射，支持松手停火。沿用已发布山猫的实际开关和弹匣配置：**10 发／匣、0.40 秒／发、4.85 秒整匣换弹**。这些是游戏手感，不是历史射速。F 型按早期的 2 cm KwK 30 L/55 命名，而不是照抄 L 型的炮名。两车可同时在车库保留。
- `Panzer_II_Ausf_F_AI.assets` 是由项目原生序列化工具生成的 Unity 敌方 GameObject 根，不是一个改名的 `.hatch`。使用与山猫相同的德军轻坦 AI/驾驶控制器，主炮、炮口、质量、碰撞体与行走部件绑定到 F 型。其 `UnitStatus.unitName` 与玩家包注册的独立 ID 完全一致；配套双方的射击模式和弹匣档案一致。AI 何时开火由原版 AI 决定。
- 完整整合包中，敌方根的 Resources 路径是 `unit/ge/panzer_ii_ausf_f/panzer_ii_ausf_f_ai`，数据路径是 `unit/ge/panzer_ii_ausf_f/panzer_ii_ausf_f_profile`。已保留 BT-7 根、巴巴罗萨通用地图和额外战役菜单；未改变已有任务的自动刷车表。

## 车辆数据来源

| 项目 | F 型游戏数据 | 说明 |
| --- | --- | --- |
| 乘员／战斗全重 | 3 人／9.5 吨 | 采用 F 型战斗重量；博物馆简表以整吨列作 9 吨 |
| 尺寸（长×宽×高） | 4.81 × 2.28 × 2.15 米 | 高度到指挥塔顶。模型保留了更高的细天线 |
| 发动机／前进极速 | 迈巴赫 HL 62 TRM，140 马力／40 公里每小时 | 公路上限 |
| 倒车／炮塔转速 | 8 公里每小时／20°每秒 | 游戏调校，沿用手动炮塔的操作方式 |
| 主武器／同轴机枪 | 20 毫米 KwK 30 L/55／7.92 毫米 MG 34 | 选用 F 型早期配置；不以博物馆展车后换的英国机枪作型号依据 |
| 俯仰 | −10°～+20° | −9.5°按游戏的整度输入取整 |
| 主炮总备弹 | 180 发 | 120 发 AP、60 发 APCR 为游戏配比；弹种性能沿用游戏山猫 |
| 装甲（前／侧／后） | 车体 35／15／15 毫米；炮塔 30／15／15 毫米 | 游戏按每方向一个数值简化 |

## 模型与验证

附件原为无贴图、无骨骼、按材质拆分的静态模型。重新识别网格连通部件，保留附件本身的车体、炮塔、火炮、机枪、履带工具、备轮与备履带，重绘深德国灰，分别处理橡胶、木柄、裸钢等材料。侧面储物箱及后车体各有一处黑心白边的直臂十字（Balkenkreuz）。标记沿着实际表面布置，并对成品逐点检查无遮挡。原件炮塔和炮盾部分面的法线与表面几乎成直角，导致黑斑；已校正并回读成品检查。

每侧五个独立悬挂的负重轮、四个托带轮、前主动轮和后诱导轮，共 22 根旋转轴。按原附件每侧 94 块活动履带板的中心和外沿重建闭环；用单块原始履带板烘焙纹理，左右履带沿各自的走向滚动。车头挂的备用履带保留在车体上。模型具有炮塔旋转、炮架俯仰、炮管后坐、同轴机枪独立炮口及三段演示动画。GLB 演示通过悬挂蒙皮使履带贴合；手机游戏使用相同轴位的原生悬挂与分侧纹理滚动，不会直接播放 GLB 的蒙皮动作。

实际 `.hatch` 已交给仓库的原生加载、模型和材质绑定代码运行，以模拟 Unity 对象验证引用；按住／松手回归和基于该包数值的 10 发换弹回归通过。再次打开已注册的 UnityFS 核对 F 型和 BT-7 的 GameObject、配置、贴图和依赖，旧资源与关卡均保留。预览是本次 GLB 的 Blender 实渲；未作安卓实机实战测试。

## 工程复现

仓库内 `tanks/Panzer_II_Ausf_F` 是已完成、可直接打包的工程。从根目录运行：

```sh
python -m hatch tanks/Panzer_II_Ausf_F --output out/Panzer_II_Ausf_F.hatch
PYTHONPATH=. python tests/test_panzer2f.py --project tanks/Panzer_II_Ausf_F --hatch out/Panzer_II_Ausf_F.hatch --apk /path/to/Hatch-0.4-Grille-HE200-T26.apk --report out/rig-qa.json
python -m tankbuilder.bt7.prefab --vehicle-id Panzer_II_Ausf_F --data /path/to/stock/data.unity3d --hatch out/Panzer_II_Ausf_F.hatch --existing-index /path/to/BT7/Hatch-Enemy-AI-index.json --out out
python -m tankbuilder.panzer2f.integration --apk /path/to/Hatch-0.4-Grille-HE200-T26.apk --base /path/to/stock/data.unity3d --previous /path/to/BT7-Integration.zip --player out/Panzer_II_Ausf_F.hatch --ai-dir out --out out/combined
```

若从原附件重新分件，可使用 `python -m tankbuilder.panzer2f.build --source /path/to/panzer_ii_light_tank_-_toshueyi.glb --project out/project`（除项目已有依赖外，读取原网格连通部件使用 SciPy）。渲染入口为 `blender -b -P scripts/render_bt7.py -- --project out/project --out out/render --motion`，制图与视频为 `python scripts/panzer2f_preview.py --render out/render --out out`。

## 实车参考及署名

- [The Tank Museum：Panzer II，馆藏 F 型与照片](https://tankmuseum.org/tank-nuts/tank-collection/panzer-ii)；[John Rickard：F 型馆藏实车右侧高清照片](https://www.historyofwar.org/Pictures/panzer_II_ausf_f_right2.jpg)。
- [Preserved Tanks：博文顿 28434 号 F 型，照片与侧箱／车尾十字位置记录](https://preservedtanks.com/Profile.aspx?Select=124&UniqueID=89)。本次选择单色德国灰，不照搬展品后期重涂的灰棕迷彩或部队编号。
- [Quartermaster Section：F 型备弹、尺寸、装甲、成员及数据](https://www.quartermastersection.com/german/afvs/431/PZIIAsufF)；[《German Light and Medium Tanks》：Model F 的轮系和 140 马力发动机](https://erenow.org/ww/german-light-and-medium-tanks/3.php)。
- 附件原模型由 **Joanthan To（Toshueyi）** 创作：[Panzer II Light Tank - Toshueyi](https://sketchfab.com/3d-models/panzer-ii-light-tank-toshueyi-e237b8939e4343aba3b9c55afed86321)，[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。本次改编包括重分部件、尺寸校准、法线修正、纹理与标记、履带重建、骨骼绑定、游戏配置。历史照片只用于参考，未嵌入车辆纹理。
