# 巴巴罗萨行动 · 西波列西亚乡野

这是一张供多个任务共用的 1.4 × 1.4 公里地图，表现 1941 年初夏西波列西亚一带的村庄、条田和河漫滩。布局是原创的，没有照搬具体战场。地图不内置敌我单位、胜负条件或出生点；未来的任务可以各自选用地标。现有「额外战役」标题页与本地图独立，不会因加入地图库而自动开始任务。

## 地图内容

村庄沿东西向土路分布，木屋后有谷仓、棚屋和菜圃。村口宽木桥连接两岸；北侧另一座较窄的农桥通往河漫滩，构成一条能绕回村庄的路。南侧是池塘和农庄，东岸有磨坊，零星果树、芦苇与外围林带构成过渡。七条道路有不同宽度和坡度。

| 场景内的原名 | 用途 |
|---|---|
| `Field_Polesie` | 原生 Unity Terrain、TerrainCollider；两者共用同一份 TerrainData。原点在西南角，地图中心为 X/Z = 0，正 Z 为北。 |
| `crossings` | 两座静态木桥；分别有桥面和两侧护栏碰撞盒。 |
| `Mission Anchors` | 11 个没有阵营和逻辑的地标，名字及世界 XYZ 坐标见 map.json；地标不是实际出生点。 |
| `Map Preview Camera` | 场景自带的日间观察相机。任务接入玩家相机时应关闭它，以免画面重复渲染。 |
| `Field Wall` | 与原版相同的四侧边界。 |

## 原版和史料依据

从所适配游戏的 Field_04（玩家场景 level11）量取地块尺寸、地形采样密度、碰撞层级和树木 LOD。新地图采用 257 × 257 个高度样点、512 × 512 四通道地表权重，沿用游戏的草地和泥路材质、分级树木、白天光照以及原版水面资源。村屋、风磨坊、篱笆、木桥和芦苇为本图新做；道路在地表上绘制，桥面则是独立碰撞体。没有复制原村庄的道路布局。

- [Changes in the physiognomy of the landscape of West Polesie from the middle of the 19th century till the beginning of the 21st century](https://up.lublin.pl/files/biologia/Struktura/14Krajobrazy/publ/d4_changes.pdf)：河流、草甸、田地与村落的关系，传统木屋及宅旁菜圃。
- [Louise Arner Boyd，1934，Belarus, row of houses along cobbled street（UWM American Geographical Society Library）](https://collections.lib.uwm.edu/digital/collection/agseurope/id/4657/)：参考木屋的体量与临街排列；没有照搬照片中的铺石街面。
- 图中的林地位置、桥的数量、路线走向和房屋坐标都是为本游戏设计的。

## 生成和使用

地图资源包里的 `level21` 是 Unity 玩家原生场景；`globalgamemanagers` 是对应基底的场景登记表，原有 0–20 号场景的索引不变。`Minimap_Polesie_600.png` 是北朝上的无文字小地图，供任务 HUD 引用；没有修改原版 HUD。另发的 GLB 是同一地形和物件坐标的离线预览，可用 Blender 或支持 glTF 2.0 的查看器打开。GLB 用静态水面、烘焙的地表颜色和固定级别的树木；手机客户端由原版着色器与 LOD 控制显示。

仓库根目录安装 `requirements-builder.txt` 中固定的构建工具后运行：

```bash
python -m tankbuilder.barbarossa --source /path/to/data.unity3d --output /path/to/Polesie --check-container
```

源文件也可以是适配的 Hatch 0.4 APK。在同一命令加 `--unity-data /path/to/new-data.unity3d` 会输出合入地图后的 Unity 数据，但不构建 APK；该路径不得已存在。若源数据已包含上一版「额外战役」标题页，合并会保留它。在接入现有模组时使用目标版本的原数据生成注册表，不要用资源包里的示例注册表覆盖另一版本的管理资源。若 21 号场景已被占用，生成器会停止。加 `--render-inputs` 后可用 `blender -b -P scripts/render_barbarossa.py -- --field-dir /path/to/Polesie --output /path/to/views` 离线渲染村口、木桥和磨坊。可选的 `--labeled-overview` 生成中文总览，需要本机安装 Noto Sans CJK 字体。

## 已验证的范围

`verification.json` 记录这次输出的检查。验证从序列化后的场景回读地形、地表权重、树木与建筑引用、父子关系和碰撞盒，按不超过 2 米的间距采样七条道路，检查积水、固定障碍、桥面以及桥头高差。另用 Unity 资源读取器重新打开合并后的 UnityFS 数据，核对新增场景、原管理器和未修改资源。Blender 预览不等同于 Unity 或 Android 实机测试；车辆实驶、手机帧率及任务 AI 寻路还需在接入具体任务后验证。
