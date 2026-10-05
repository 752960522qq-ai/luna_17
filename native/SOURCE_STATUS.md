# 当前原生模块源码状态

本目录保留远程构建器 2.0 源码，包含基于 r6 的多车型配置改动。交付版本 r9 的原生模块来自 r7，并在 r8/r9 保持不变。r7 本地源码改动尚未推送就被工作区维护清理，不能用本目录源码重编来声称复现当前模块。

当前模块：`prebuilt/5.1.0/r9/libaotmod.so`。

SHA‑256：`d01d0a331d8517e6901a04e5b4874b3cac2e40ca7e4427a866eccf424f49dc86`。

对应既有 ARM64 回归记录：`reports/r9/native-tests-carried-forward.json`（17 项通过，模块指纹一致，本次未重新执行）。当前重建使用 `scripts/package_t54_r9.py` 的快照流程。
