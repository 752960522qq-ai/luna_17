# Panzer III Ausf.F · 三号 F 型

这是一辆独立的德国 Tier II 中型坦克，使用外置炮盾的短身 5 cm KwK 38 L/42 构型。车体长 5.38 m，宽 2.91 m，高 2.44 m；含炮管的模型全长约 5.50 m。5 人、19.8 t、40 km/h。正/侧/后：车体 30/30/21 mm，炮塔 30/30/30 mm。装填时间、载弹分配、伤害数值和转速为游戏设定。德国灰取自 RAL 7021 色系，炮塔与上车体的左右侧采用黑芯白边直臂十字。

- 实车：[照片与外置炮盾](https://www.worldwarphotos.info/gallery/germany/tanks-2-3/panzer-3-tank/panzer-iii-61316/)、[车辆尺寸、重量与装甲](https://www.historyofwar.org/articles/weapons_panzer_III_ausf_F.html)、[发动机](https://panther-panzer.de/PanzerIII/PanzerIIIf.htm)、[德国灰沿革](https://panzerworld.com/german-armor-camouflage)。
- 模型：TigerAce1945 的 [Panzer III Pack REVISED](https://cults3d.com/en/3d-model/game/panzer-iii-pack-revised)，使用用户提供的包内 `PZ3_AusfF.zip`。公开代码仅包含转换工具与自编配置；原始 STL、生成模型、预制体及预览在私人交付中。
- 运行时有 12 个独立负重轮悬挂支点、6 个托带轮、2 个主动轮和 2 个诱导轮。两侧履带有各自的滚动材质。开火点与后坐节点分离，玩家瞄准使用原版 `Turret/Gun` 层级。
- 玩家 Hatch 目录和 Unity Resources 中的原生玩家、AI、简介各自独立注册；不替换原版三号 J，不改既有地图或战役出场名单。

从仓库根目录运行，并使用本仓库既有的生成工具和依赖：

```sh
veh=tanks/Panzer_III_Ausf_F
python -m tankbuilder.panzer3f.build "$MODEL_SOURCE" "$veh"
python -m tankbuilder.panzer3f.verify "$veh"
blender -b -P scripts/render_bt7.py -- --project "$veh" --out "$RENDER_DIR" --motion
python scripts/panzer3f_preview.py "$RENDER_DIR" "$PREVIEW_DIR" --motion --thumbnail "$veh/thumbnail.png"
python -m tankbuilder.panzer3f.integrate --apk "$BASE_APK" --index "$PRIOR_AI_INDEX" --project "$veh" --out "$STAGING_DIR"
```

最后一步在暂存区写入两份 Unity 序列化预制体、累计的 `assets/bin/Data/data.unity3d`、车库模块及目录、AI 目录及可重放的增量。APK 只用作输入。暂存区中的 `assets` 是覆盖层，沿用基础游戏的其他文件。

如有已交付的三个私人运行文件，可跳过转换，从相同基线恢复归档好的资源。命令校验基础游戏、车辆模块、原始目录和恢复后的总数据散列：

```sh
python -m tankbuilder.panzer3f.restore --apk "$BASE_APK" --integration PanzerIII-F-Integration.json --overlay PanzerIII-F-Resources.overlay --vehicle Panzer_III_Ausf_F.hatch --out "$STAGING_DIR"
```

外观修订：按外置炮盾的实车照片收细打印模型偏粗的外露炮管。炮口处模型外径相对首版减小 43%，炮根保留阶梯轮廓；炮盾、炮口位置、后坐行程及所有车辆和武器数据保持原值。这是对游戏轮廓的修正，不是实车外径测量。
