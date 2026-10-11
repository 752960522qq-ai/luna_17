# 蟋蟀与锁定语音修订（源码，不构建 APK）

## 修复

- 蟋蟀原始模型 SHA 与已有源模型一致。原游戏模板使用 `Mobile/Bumped Specular`，该着色器只有 `_MainTex/_BumpMap/_Shininess`，没有 `_Color`：纯色材质失去原始底色，JPEG 的不透明 alpha 又成为全强度高光。模型加载改用游戏资源中已经保留的 `Standard`，重置模板贴图/关键词和高光，应用每个材质的底色。编译器为非履带的双面材质输出反面几何及反向法线，保留开放战斗室内面；原贴图字节和 UV 保留。
- 原枪口距整车信息碰撞体前沿仅约 5mm，后坐又会把挂在 Barrel_Recoil 下的 launcher 拉回车内。launcher 改挂稳定的 Gun 转轴，沿炮口前移 0.15m；barrelTrf 继续绑定真实后坐轴。ShellMove 原实现只排除一个自身碰撞体；新 ImpactProcessing 包装器排除发射车根 Transform 下的所有碰撞区域，敌车、地形仍走原命中处理。AttackInfo +0x20 是发射者 Transform，先从该 Transform 查 UnitStatus 再核验模组身份。
- 移除独立火炮镜按钮。读取原 CameraControl 的 scoped 状态、原始倍率数组及 CurrentZoomIndex：火炮的 5x 档进入鸟瞰，2.5x 保持平射。退镜恢复原倍率对应 FOV。鸟瞰手势可在画面中央进行单/双指平移、双指缩放；抬起手指按 pointer ID 重新建立基线，避免跳动。左右原游戏控制与顶部工具栏保留触摸入口。
- 新语音源采用用户提供的 `语音.zip`，构建时按文件夹建立配置、校验源摘要并输出扁平 WAV 资源，Android 解包规则继续检查路径、大小及 WAV 头。普通事件从所属池随机选择一条；不连播池内所有变体。
- 事件 17“锁定该敌人”：瞄准活着且可见的敌方坦克或飞机时，只播目标类型 → 相对车体钟点 → 距离前缀 → 最接近的可用距离数字。小于 300m 改播平射，不加距离前缀和数字。持续瞄准同一目标不循环播报；换敌人会再次触发，丢失目标 0.5 秒后重新锁定可再次触发。播放期间丢弃新事件，不排队补播。
- 战斗开始、打穿、被打中、胜利、击毁、切换 AP/HE/APCR/WP/HEAT、未命中的上下左右修正按用户命名池映射。未命中根据已锁定目标和炮弹最近采样位置判定方向。伤害小于 10 的事件保留，但新包未提供未击穿池，默认静音，不再误播“命中”。

## 验证及边界

详见 verification.json。执行生产 C 绑定器、碰撞包装器、原倍率选择器、语音语义观察器及 JVM 播放/手势/模块加载测试，编译完整 Java 源码，并验证 55 项 Unity API 确实保留。ARM64 shell 检查执行了游戏真实的初始化倍率与重力指令片段。用于模拟器的 ARM64 构建不是 Android 发布库；此次未生成 APK。

未连接 Android 设备，因此没有手机端 GPU、真实触摸分发或长时间对局验证，不能将这些自动检查称为实机验证无误。距离录音只覆盖 300–2000m；超出范围不伪造数值。原始语音及私钥不提交 Git，构建时需使用本次语音源。

可重复检查：

```sh
python3 scripts/restore_t54_model.py --model tanks/Grille/model.glb
python3 scripts/restore_t54_model.py
python3 -m unittest tests.test_grille_materials tests.test_crew_packages tests.test_crew_voice_player tests.test_artillery_gesture tests.test_gameplay_packages tests.test_vehicle_kinds tests.test_projects tests.test_feature_dependencies
# 每个 tests/test_{crew_events,crew_gate,continuous_fire,experience_math,artillery_scope,shell_self_collision}.c 用 gcc -std=c11 -O2 ... -lm 编译并运行。
# JVM JNI 检查须走其 CLI：python3 tests/test_module_loading.py --jni-include <JNI include>
```
