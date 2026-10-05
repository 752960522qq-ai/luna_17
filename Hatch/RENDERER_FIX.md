# Hatch 0.1 渲染器查找修复

手机反馈：替换 T54 时显示 `T34 renderer template missing`。

`GetComponentInChildren` / `GetComponentsInChildren` 原先仅按名字和参数数量查找，可能选中泛型或列表重载。现在明确匹配第一个参数的 `System.Type` 类；Unity 调用异常不再覆盖为模板缺失。没有材质时给出独立错误。

验证：生产助手函数在误导重载排在前面的测试中通过 4 项检查；原查找方式在同一场景失败。新 ARM64 库通过 12 项 Unicorn 检查，安装器通过 9 项检查。APK 原始 613 项载荷保持不变，签名及 16KB 对齐检查通过。

未连接 Android 真机，不能据此确认 Unity 中模型、贴图及操控全部正常。保持加载失败时回退原坦克。

独立 T54 模组格式仍为 Hatch 0.1：包含 GLB、贴图、参数、绑定配置及运行时数据，无须修改。修复的是加载器，需更新游戏 APK 后再加载。
