# Hatch 0.1 子物体组件修复（第二次）

手机反馈：`Unity method unavailable: GetComponentsInChildren`。第一次修复仅解决重载歧义；它的模拟测试没有覆盖实际游戏裁剪后的 API。

对原版 5.1.0 的加密元数据解码后验证：GameObject 保留的 `GetComponentsInChildren` 全部为泛型重载，没有非泛型 `(Type, bool)`。非泛型 `GetComponentsInternal` 六参数实现仍然存在（token 0x60009ee）。

现在直接调用 `GetComponentsInternal(type, false, true, true, false, null)`，获得匹配类型的子物体组件数组，包含未激活对象。继续按第一个参数 System.Type 匹配，保留实际异常，并保持失败回退。

命名：修改器界面和 Android 应用名恢复为“坦无敌3000”；Hatch / 舱盖 0.1 仅用于模组加载器及管理界面。模组文件及目录格式不变。

验证：实际元数据 3 项检查，生产调用助手 4 项检查，ARM64 执行 12 项检查。Android / Unity 真机显示和操控尚未验证。
