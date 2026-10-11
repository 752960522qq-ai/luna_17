> 已并入“更好的坦克体验0.1”。本目录仅保留旧包兼容资料，正式构建不再单独打包成员体验。

# 更好的成员体验

使用上传的 `中系新语音.zip`（641 个 WAV），不包含旧成员语音。`voice-inventory.json` 记录逐文件长度和 SHA-256，`audio-source.json` 记录原始 ZIP 的摘要。

构建独立玩法包：

```bash
python -m hatch.features mods/better_crew_experience --output dist/better_crew_experience-0.1.hatch --voice-archive /path/to/中系新语音.zip
```

完整前置及玩法模块的构建使用 `scripts/build_mods.py --voice-archive /path/to/中系新语音.zip`（另需 NDK、Android SDK 和 D8 参数）。该脚本仅构建 loader DEX / 模块 `.hatch`，不创建 APK。原始上传音频作为用户提供的构建输入，不加入 Git 历史。

需要本次更新后的舱盖加载器和坦无敌3000前置（支持 `crew-voice-v1`）；旧前置不能独立加载此包。它与“更好的坦克体验”是两个玩法包，依赖同一个前置，可同时加载。

播放规则：从第一片段开始直到最后片段结束，所有新触发直接丢弃。片段切换时保持同一把锁；不排队、不打断，也不会结束后补播。媒体读取失败或模块退出会释放锁。

`features.json` 中的默认事件对应原版 RadioVoice：

| 事件 | 原事件 | 新语音 |
|---|---|---|
| 0 | CopyThat | 确认 |
| 1 | EnemySpotted | 目标报话 |
| 2 | FireAtWill | 开火 |
| 3 | Hostiles | 目标报话 |
| 4 | EngagingEnemy | 开火/交战 |
| 5 | StayLow | 包内无对应片段，静默 |
| 6 | CoverMe | 包内无对应片段，静默 |
| 7 | ManDown | 成员损失 |
| 8 | ObjectTaken | 包内无对应片段，静默 |
| 9 | TargetDestroyed | 目标摧毁 |
| 10 | 玩家主炮发射 | 炮手开火 |
| 11 | 玩家装填完成 | 主炮就绪 |
| 12～16 | 装填开始，按当前选用弹种 | AP / HE / APCR / 烟雾（WP）/ HEAT 装填报话 |

目标报话按“目标 → 实际识别到的目标类型 → X 点钟方向 → 距离引导 → X 米”连续播放。方向相对玩家车体正前方计算，距离来自炮塔当前瞄准点；目标类型通过瞄准点附近的敌方载具识别，无法确认时播通用敌人片段。距离只使用包内实际存在的数字，并限制近似误差；没有合适数字就省略距离，不拼出错误数值。T34、Tiger、Panther 有专用片段，其他坦克/飞机使用对应通用类型。

原包中没有发现 StayLow / CoverMe / ObjectTaken 的对应素材，默认不拿“停车”“前进”或“战斗胜利”错配这些事件，可在 events 中补入后自行映射。

只替换原版无线电成员语音入口及自动回话，保留炮声、发动机、装填音效和音乐。功能用于离线战斗；在线场景沿用原游戏入口。
