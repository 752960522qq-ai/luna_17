# T‑54 (1949) 玩家 Tank Pack

此目录记录用户指定参数。实际模型与 `rig.json` 随 `T54_1949.tankpack` 交付；资源适配器只支持原始 Attack on Tank 5.1.0 ARM64 的已审核资源指纹。

进入单人对局后，打开 MOD 菜单 → 对局换坦克 → 苏联 → T54_1949_Player → 替换当前坦克。它暂时只供玩家使用，没有加入 AI 阵容或原游戏的常规研发菜单。

模型保留用户提供的默认涂装，车体、炮塔、火炮、后坐炮管分离。总长 9.00 m、车宽 3.27 m、主要车体/炮塔高 2.40 m；顶部附属设备高于该高度。

GLB 内包含展示动画；游戏里炮塔俯仰与后坐使用原控制器，轮子、履带和射线悬挂由当前版本原生适配处理。预览图是实际导入模型的渲染，不能替代真机截图。

SGMT 的 x30 映射为游戏弹药单位。未提供 HE 穿深和精确车体转向速度，因此沿用模板对应规则。音效复用游戏中的 100 mm 炮、机枪、引擎、炮塔及装填样本，没有声称是 D‑10T/SGMT 的真实录音。

```bash
python -m tankbuilder tankpack T54_1949.tankpack
python -m tankbuilder prepare-assets original.apks --tankpack T54_1949.tankpack --out build/T54-assets
python -m tankbuilder build original.apks --config builder.config.json --tankpack T54_1949.tankpack --output dist/Attack-on-Tank-T54-r5.apk
```

新版本必须重新检查原生 ABI、序列化结构、模板及目录，不能直接复用旧资源包中的 data.unity3d。
