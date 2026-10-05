# Hatch 0.1 独立接入包

新增包体内置坦克目录释放逻辑：首次启动校验 assets/Hatch/catalog.json 并将 .hatch 复制到外置 Hatch/mods；已有 ID 保留、删除后不恢复同一内置版本、错误摘要拒绝。

完整独立交付件是 Hatch-0.1-standalone-package.zip，包含预编译 DEX/原生库、固定适配器、自动接入脚本、Android 签名工具、T54 示例包及说明。脚本把程序放到 APK 的 DEX/native 标准位置并修改启动入口；单纯复制 assets 文件夹不会启动加载器。

本次交付真实测试 APK：Attack-on-Tank-Hatch-0.1-standalone-test.apk。

验证：9 项接入脚本测试，5 项真实 Java 释放逻辑检查（Android Context/SharedPreferences 边界替代），原始载荷保持、DEX/manifest/签名/对齐校验。原生核心未变，尚未安卓真机测试。不是 r9 修复版替换。
