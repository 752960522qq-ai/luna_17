# 额外战役：巴巴罗萨行动

首页菜单第二项「额外战役」打开独立战役页，左下角的原版坦克图标返回首页。原「战役」仍进入原来的模式。新页面暂时只显示「暂无可用任务」；不会启动关卡，也不读取或改写战役进度。

入口沿用首页战役按钮的普通态、高亮态、按压动画和点击音效配置。新页使用原版战役选择页的中文标题样式、居中任务栏和返回控件，背景沿用游戏首页的原图。两个新按钮使用 Unity 自带的 `Button.onClick` 切换界面并交接焦点。新文案不继承原「战役」的翻译键，切换语言后也不会被旧标题覆盖。原中文字体和设备上的中文回退沿用游戏行为。

## 生成独立的标题场景

按仓库的 `requirements-builder.txt` 安装依赖后，在仓库根目录运行：

```bash
python -m tankbuilder.extra_campaign \
  --source /path/to/Hatch-0.4-Grille-HE200-T26.apk \
  --output /path/to/Hatch-Extra-Campaign

PYTHONPATH=. python tests/test_extra_campaign.py \
  --source /path/to/Hatch-0.4-Grille-HE200-T26.apk \
  --scene /path/to/Hatch-Extra-Campaign/level0
```

`--source` 也可传入该包里的 `data.unity3d`，或同时放有原始 `level0`、`level1`、`globalgamemanagers.assets` 的目录。三个输入都必须匹配适配器的指纹，防止用错版本或覆盖另一份已改的首页。生成器只向输出目录写入 `level0`，不需要密钥或 Android 构建工具。保留资源名 `level0`；将来合入时，它替换 **UnityFS `assets/bin/Data/data.unity3d` 内的 `level0`**，不是 APK ZIP 根目录中的一个新文件。该场景额外引用现有的 `sharedassets1.assets` 以使用原版任务栏图，不需要另发贴图或修改关卡场景。

## 已验证的范围

从上述 APK 和从松散场景生成的 `level0` 逐字节相同。回读验证覆盖：首页入口顺序、原按钮事件不变、标题与空状态文案、控件归属、原字体和精灵引用，以及连续三轮进入和返回。布局按原版 `CanvasScaler` 检查了 16:9、20:9 和 4:3。原场景只改两处子节点列表、六个原按钮的高度和菜单行距，其余原对象数据不变。没有运行 Unity Play Mode 或 Android 实机测试。
