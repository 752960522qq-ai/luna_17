# 四号 C 型中型坦克 · Panzer IV Ausf.C

Hatch 0.4、Attack on Tank 5.1.0 ARM64、「坦无敌3000」1.0。玩家包独立编号为 `Panzer_IV_Ausf_C`。游戏里的单发主炮、带装甲护套的同轴机枪、成对负重轮区分了这辆车与二号 F、二号山猫和原版四号 H。

## 玩家车和关卡敌车

- 手机：「模组管理 → 导入 .hatch」选择 `Panzer_IV_Ausf_C.hatch`。完全退出并重启游戏后，在模组坦克中选择 **Panzer IV Ausf.C**。
- 敌方原生 Unity 预制体：`Panzer_IV_Ausf_C_AI.assets`。沿用原版四号 H 的德军中坦 AI 驾驶控制，替换车体、碰撞、炮塔与炮口、16 个悬挂接点和武器数据。保留 AP 和 HE 两套游戏弹丸池；同轴机枪引用自己的炮口。
- 关卡从 `unit/ge/panzer_iv_ausf_c/panzer_iv_ausf_c_ai` 取得敌方实例。资料路径为 `unit/ge/panzer_iv_ausf_c/panzer_iv_ausf_c_profile`。导入玩家包就能驾驶；使用敌车需要整合包的游戏资源。不会自动给现有任务加刷敌点。
- 累积整合基于上一版二号 F，保留 BT-7、二号 F、原有“额外战役”入口、巴巴罗萨地图及此前的模组目录。完整 AI 索引从 10 辆增加到 11 辆；近期三辆车的玩家包和原生敌车均附在整合包中。

## 录入数据

| 项目 | 游戏值 | 依据或取舍 |
| --- | --- | --- |
| 阵营、类型、等级 | 德国中型坦克，Ⅱ 级 | 等级按游戏设定 |
| 尺寸 | 长 5.92、宽 2.83、高 2.68 米 | 高度到指挥塔，不计天线 |
| 乘员和战斗全重 | 5 人，18.5 吨 | 采用 C 型标准表 |
| 动力、公路极速 | Maybach HL 120 TRM，300 马力，42 公里/小时 | 选用后期 C 型发动机；采用 Panzernet 同一张规格表 |
| 倒车、炮塔回转 | 8 公里/小时、18°/秒 | 游戏调校 |
| 主炮、俯仰 | 短身管 75 毫米 KwK 37 L/24，−10° 到 +20° | 单发，游戏装填 5.0 秒 |
| 主炮备弹 | 80 发：30 AP、50 HE | 总数参考早期 B/C 型车体；弹种配比、伤害与装填为游戏平衡值 |
| 副武器 | 1 挺同轴 MG 34；游戏机枪弹药字段 30 | 没有外装的车体球形机枪 |
| 车体及炮塔前／侧／后 | 30／15／15 毫米 | 采用未加附加装甲的 C 型；实车 14.5 毫米按 Hatch 整数字段取 15 |

## 模型及绑定

使用用户给的 patoburro 原始 GLB。原文件只有按材质合并的静态节点。保留原贴图的 UV 和表面细节，重新调成德国深灰；轮缘、履带和工具与车体有色差。两侧车体及后部的黑白直臂十字（Balkenkreuz）投到实际露出的装甲面上。两侧工具布局不同，标记尺寸和位置随各自面板调整。参考照片用来看构型和标记，未嵌入交付纹理。

炮塔绕原座圈旋转；炮架绕耳轴俯仰；短炮管向后复进，机枪不随主炮后坐。每侧八个双轮缘负重轮分属四个双轮板簧总成，另有四个托带轮、一个前主动轮和一个后诱导轮。28 根轮轴各有自身半径，16 个地面接点都可运动。保留原履带上支段的下垂、前后转折和原履带图案；左右独立滚动。

GLB 含轮转、悬挂、炮塔与火炮三段动画。离线预览中履带的下支段有接地蒙皮；Hatch 游戏使用原生轮组悬挂和分侧履带纹理滚动。资料中的视频是实际导出模型的离线渲染，不是手机录像。

## 回读验证

从交付的 .hatch 重新获取渲染网格、所有贴图及控制标记，检查 28 个轴心、16 处轮带接触、前进／倒车／原地转向的履带方向、枪炮口是否分开和十字不被其他零件遮挡。仓库原生加载器用模拟 Unity 对象实际执行材质、炮口、车轮和武器绑定。敌车从最终的原生文件中回读，验证只有敌方控制器，并检查 AP、HE、机枪、贴图与碰撞。整合数据逐字节校验旧关卡和已发布的两辆车，重读新增资源，并对结果作 SHA-256 校验。没有进行安卓真机对战。

## 复现

从仓库根目录执行。车辆构建使用项目本身的 hatch、Unity 资源工具；从原附件复现识别和重涂需要 NumPy、SciPy、Pillow 和 pygltflib。仓库已包含可直接打包的成品工程。

```sh
python -m tankbuilder.panzer4c.build --source /path/to/pz_kpfw_iv__ausf._c.glb --project out/project
python -m hatch tanks/Panzer_IV_Ausf_C --output out/Panzer_IV_Ausf_C.hatch
PYTHONPATH=. python tests/test_panzer4c.py --project tanks/Panzer_IV_Ausf_C --hatch out/Panzer_IV_Ausf_C.hatch --report out/rig-qa.json
python -m tankbuilder.bt7.prefab --vehicle-id Panzer_IV_Ausf_C --data /path/to/stock/data.unity3d --hatch out/Panzer_IV_Ausf_C.hatch --existing-index /path/to/PanzerII-F/Hatch-Enemy-AI-index.json --out out
python -m tankbuilder.panzer4c.integration --apk /path/to/Hatch-0.4-Grille-HE200-T26.apk --base /path/to/stock/data.unity3d --previous /path/to/PanzerII-F-Integration.zip --player out/Panzer_IV_Ausf_C.hatch --ai-dir out --out out/combined
python -m tankbuilder.panzer4c.kit --integration out/combined --previous /path/to/PanzerII-F-Integration.zip --ai-dir out --verification /path/to/QA --out out/PanzerIV-C-Integration.zip
```

## 照片、资料和模型署名

- [C 型前部的时期照片，Panzernet / World War Photos](https://www.panzernet.net/domains/panzernet.net/panzernet/fotky/tanky/pz4/doclanku08.jpg)：核对短炮、同轴机枪护套、早期炮盾和轮组。
- [History of War：东线渡河中的四号 C 型](https://www.historyofwar.org/Pictures/pictures_panzer_IV_ausf_C.html)：核对德国灰车辆侧前方的直臂十字布置，未复刻部队编号。
- [Panzernet：分型资料与规格对照表](https://www.panzernet.net/domains/panzernet.net/panzernet/en/tanky/pz4.php)；[Tank Archives：A 到 C 型的差异与发动机变更](https://www.tankarchives.com/2017/01/pzkpfwiv-ausf-through-c.html)；[German War Machine：每侧八轮成对板簧](https://germanwarmachine.com/weapons-technology/tracked-vehicles/panzer-iv-ausf-c.html)。
- 原始模型：[Pz Kpfw_IV_ Ausf._C](https://sketchfab.com/3d-models/pz-kpfw-iv--ausf-c-8c6502b1ddf7484a91a2bf529ee8295e)，作者 **patoburro**，授权 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。本次改编：德国灰重涂、标记、拆分及校准轴位、履带 UV、绑定及游戏适配。
