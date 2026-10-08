# 舱盖 Hatch 0.3

适用：突击坦克 5.1.0，Android ARM64。前置模组仍为坦无敌3000 1.0。
更新已有安装时先导入本次附带的前置 hatch 并重启游戏；加载器保留用户已导入的前置，不会自动覆盖旧版本。
APK 内置新前置，不内置坦克模型模组。

## 新类型

| tank.json.vehicleKind | manifest.json.basePrefab | 行为 |
| --- | --- | --- |
| tank（默认，可省略） | T34_85_Player | 常规旋转炮塔、履带驱动 |
| tank-destroyer | SU_85_Player | 固定战斗室、有限水平炮架射界、履带驱动 |
| towed-gun | ZiS_3_Player | 原版牵引组件、双轮随位移转动、无自主动力 |

新增类型必须设置 tank.json.gunTraverseHalfAngle，整数 1–180，单位为度，表示左右各自的最大射界。例如 15 表示左15°、右15°。gunElevation、gunDepression、turretRotation 仍分别控制仰角、俯角和炮架旋转速度。

牵引火炮要求 enginePower、maxForwardSpeed、maxReverseSpeed 均为 0；rig.wheels 必须包含左右各一个 roadWheel，rig.tracks 为空。车轮本地 X 轴应对准轮轴，轮心与原点重合。
两类新增模板沿用原版 SU-85/ZiS-3，不带同轴机枪；weapon.machineGun.ammo 必须为 0。保留同轴机枪字段仅用于旧协议兼容。

## 模型与 rig

常规坦克继续使用 Hull → Turret → Gun → Barrel_Recoil。
新类型使用 Hull → GunMount → Gun → Barrel_Recoil。GunMount 必须是没有网格的空节点，位于水平旋转支点；固定战斗室、护盾及车体零件绑定到 Hull；随俯仰的炮管及零件绑定到 Gun；后坐部分绑定到 Barrel_Recoil。
rig.json 新类型使用 mount 字段替代 turret，格式例如：

```json
{"mount":{"node":1,"pivot":[0,1,0]}}
```

其余既有 rig 字段仍需提供；驱逐战车需要左右履带及至少四个负重轮。可以通过标准节点名自动推断 rig，也可以显式提供完整 rig.json。

Python 构建工具入口保持不变。先验证项目，再通过 hatch.pack 的 pack_project 生成 hatch。新类型包需要 0.3 APK 和本次前置；0.1/0.2 的旧坦克包仍可读取。资源包内的 runtime.bin 头部继续保持版本1，类型和射界写入28字节的可选尾部。

## 资源声明位置

APK：assets/Hatch/RESOURCE_USAGE.txt。
首次启动后：Android/data/com.LabenekoGames.Project_02/files/RESOURCE_USAGE.txt。
内容保留用户提供的完整资源使用声明和五个模型来源链接。该声明不替代各资源自身的作者署名与授权材料。

## 验证边界

已执行生产 ARM64 代码的模拟测试，覆盖原版模板选择、原版水平射界限位、牵引火炮车轮随前后位移转动、停止与瞬移保护；执行了三类资源包解析与模型绑定检查，以及前置 ClassLoader/JNI 回归检查。HE 弹池来自原版素材，保存后仅两处 Launcher 与对应父 Transform 四个旧对象发生变化。
未执行实际安卓设备上的启动、战斗及牵引操作试跑；原版牵引组件被保留，没有新增牵引车辆或牵引按钮。新增类型尚未扩展为模组 AI 敌人生成。
