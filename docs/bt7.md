# BT-7（1937 年型）｜Hatch 0.4 / Attack on Tank 5.1.0

本车使用附件双车 GLB 中蓝灰底色的锥形炮塔车体，单独保留 BT-7；白色直壁炮塔的另一辆没有导入。改为苏联橄榄绿，覆盖原虚构校徽，在炮塔两侧斜装甲上各投影一枚红五角星，两颗星与炮塔一起转动。文件名和模组 ID 为 `BT7`；车库名称为 `BT-7 (1937)`。这个玩家模组和 AI 共用同一份模型、轮轴、贴图及车辆配置。

## 玩家车与 AI

已有 Hatch 0.4 及「坦无敌3000」1.0 的 5.1.0 客户端：在模组管理中点「导入 .hatch」，选择 `BT7.hatch`，完全退出游戏后再启动，从模组坦克列表选择 `BT-7 (1937)`。这一步只安装玩家车。`tanks/BT7` 本身也是可直接用本仓库打包的完整载具工程。

`BT7_AI.assets` 是 Unity 6000.3.19f1 的原生序列化文件，根节点 `BT7_AI`，角色是敌方；原版苏联 `T34_76_AI` 提供 AI、驾驶、特效和单车组件。炮塔、炮管、炮口、碰撞体、两条履带、八个负重轮均改用 BT-7 的网格、位置和引用。整合包另外注册 `unit/so/bt7/bt7_ai` 和 `unit/so/bt7/bt7_profile`。前者是供关卡实例化的 GameObject，后者是该车的游戏数据 TextAsset。未把 BT-7 加入既有关卡的自动刷车名单；单独把 `.assets` 改名为 `.hatch` 不能导入 AI。原版 AI 的初始化和游戏内最终行为还需在实机验证。

`BT7-Integration.zip` 提供玩家模组、更新后的内置模组目录、AI 原件与九辆车的索引，以及在指定版本游戏上生成已注册 Unity 数据的增量文件。此前制作的额外战役菜单 `level0` 与巴巴罗萨通用地图 `level21` 已一并保留。完整步骤见整合包内的 `使用说明.txt`。

## 车辆数据

| 项目 | 游戏内数据 | 依据 |
| --- | --- | --- |
| 国家、类型、Tier | 苏联，轻型，Ⅰ | Tier 为游戏分级 |
| 乘员、战斗全重 | 3 人，13.8 t | 1937 年型参考值 |
| 尺寸（长 × 宽 × 高） | 5.66 × 2.29 × 2.42 m | 模型按整车外包尺寸校准 |
| 发动机、履带公路极速 | M-17T，450 hp，52 km/h | 仅实现履带行驶；不采用轮式公路极速 |
| 倒车、炮塔转速 | 9 km/h，16°/s | 游戏调校 |
| 主炮、俯仰 | 45 mm 20-K，−4° 至 +40° | 历史配置 |
| 主炮备弹 | 188 发，游戏中分配为 AP | 采用无电台型总备弹量；游戏内弹种配比不是史实配发 |
| 主炮装填、同轴机枪 | 3.7 秒；7.62 mm DT | 装填及机枪弹量与游戏尺度匹配；同口径弹药沿用项目 T-26 配置 |
| 装甲（前／侧／后） | 车体 20／15／13 mm，炮塔 15／15／15 mm | 车体各面为游戏简化值，实车同一方向有多块厚度不同的装甲 |

## 绑定、原始几何与验证

`Hull → Turret → Gun → Barrel_Recoil → Muzzle_Main` 分别控制车体、旋转、俯仰、后坐与炮口。同轴机枪随炮架俯仰，不跟随后坐。两侧各有四个负重轮、一个主动轮和一个诱导轮。原附件有六个负重轮的顶点塌为一点，按附件保留的真实轴位、同车完好车轮的形状补建；炮盾、排气管、焊缝等受损部件也已修补。左右履带分别建闭合路径、分配独立材质；每圈 73 个纹理周期，避免闭环接缝跳纹。GLB 带独立轮轴、两条履带的悬挂蒙皮及三个示范动画。Hatch 游戏侧使用原生轮轴、悬挂和履带纹理滚动；不会播放 GLB 演示动作或直接使用其蒙皮。

离线验收覆盖：回读实际 `.hatch` 运行数据；前进、倒车和差速的轮带方向，静态轮带间隙及红星在两侧斜甲上的可见性；AI 根对象、脚本、父子关系、网格、材质、贴图、原生资源依赖；合并后按 Resources 路径找到同一 BT-7，并保留旧目录和地图。预览为最终 GLB 的 Blender 渲染，并非 Android 游戏录屏。未做安卓实机对战或 Unity Play Mode 测试。

## 重建

从仓库根目录运行，使用项目原有 Python 工具及固定版本的 UnityPy：

```sh
python -m hatch tanks/BT7 --output out/BT7.hatch
PYTHONPATH=. python tests/test_bt7.py --project tanks/BT7 --hatch out/BT7.hatch
python -m tankbuilder.bt7.prefab --data stock/data.unity3d --hatch out/BT7.hatch --existing-index stock/Hatch-Enemy-AI-index.json --out out
python -m tankbuilder.bt7.integrate --apk stock/Hatch-0.4-Grille-HE200-T26.apk --data stock/data.unity3d --hatch out/BT7.hatch --ai-dir out --campaign Polesie --menu Extra-Campaign/level0 --out out/integration
```

`--campaign` 与 `--menu` 是可选的；不传时只给已核对的原版资源加入 BT-7。`--data` 必须匹配已验证的源版本。若要从作者的双车 GLB 重建并渲染：

```sh
python -m tankbuilder.bt7 --source bt_5__bt_7_jatkosota_girls_und_panzer.glb --project out/BT7-project
blender -b -P scripts/render_bt7.py -- --project out/BT7-project --out out/render --motion
python scripts/bt7_presentation.py --render out/render --out out
```

## 实车参考与模型署名

- [俄罗斯胜利博物馆：1937–1939 锥形炮塔 BT-7，含馆藏照与历史照片](https://victorymuseum.ru/external-navigation/bronetekhnika/38135/)。馆方也说明，展车修复时更换过轮带；这里用它辨认炮塔，不按展车移植件改写轮系数据。
- [Preserved Tanks：库宾卡 005 号车，照片及炮塔红星记录](https://www.preservedtanks.com/Profile.aspx?Select=127&UniqueID=637)。橄榄绿与红星属于此次外观选择，未将某台馆藏车的标记推广到所有战时车辆。
- [OnWar：BT-7 Model 1937 规格与图册](https://onwar.com/wwii/tanks/ussr/su003bt7m37.html)；[Jaeger Platoon：BT-5 / BT-7 图片与资料](https://jaegerplatoon.net/TANKS5.htm)。
- 原模型：“[BT 5 & BT 7 Jatkosota (Girls und Panzer)](https://sketchfab.com/3d-models/bt-5-bt-7-jatkosota-girls-und-panzer-e03f7079630b43caae2ae2c7872a775e)”，作者 **Sankocho_DePoligonos**，[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。本项目改动包括分离单车、补模、缩放、涂装、履带 UV、绑定与游戏配置。实车照片只作参考，未烘焙进纹理或随包再分发。
