# Hatch / 坦无敌3000固定签名

从2026-10-11的 Hatch-0.3-Bundled-Updated.apk 起，本项目沿用同一开发签名。

证书SHA-256：734e17a0550eb23e3e5975dc90a7932eb513ee0e62ad4804b436cacd5f15413e

签名密钥已保存在独立的 Hatch-Repack-Signing-Key.zip 中。密钥不可提交到公开仓库。
后续构建必须提供其中的 repack-key.pem 与 repack-cert.der。不得重新生成密钥；发布前检查证书哈希。
本次签名与之前的免导入版不同，首次安装需要备份存档、卸载旧包。以后同签名版本可覆盖更新。

打包：
python scripts/repack_builtin.py --base original.apk --mod Panzer_II_Ausf_L.hatch --mod T30.hatch --output Hatch-0.3-Bundled-Updated.apk --key /private/repack-key.pem --cert /private/repack-cert.der

基础包来自用户提供的免导入版，未升级加载器或修改器。内置修改器和六个坦克，更新了二号L型与T30。
仓库分块模组可通过 python scripts/restore_texture_packages.py 恢复，恢复时验证尺寸及SHA-256。
归档、签名与内容校验通过；没有安卓实机测试。
