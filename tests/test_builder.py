import argparse
import copy
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from tankbuilder.package import GamePackage
from tankbuilder.profiles import inspect_game, inspect_method_bindings, draft_profile, generate_header, native_config_digest, ROOT
from tankbuilder.runner import run_build
from tankbuilder.tankpack import validate_pack, validate_documents

class BuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game=GamePackage(ARGS.apks);cls.report=inspect_game(cls.game)
    @classmethod
    def tearDownClass(cls):cls.game.close()

    def test_original_is_recognized_and_resource_layer_is_checked(self):
        self.assertTrue(self.report['can_build'])
        self.assertEqual(self.report['identity']['unity_version'],'6000.3.19f1')
        self.assertGreaterEqual(len(self.report['module_fingerprints']),18)
        self.assertTrue(self.report['identity_and_payload_checks']['unity_data_sha256'])
        self.assertEqual(len(self.report['method_bindings']),2)
        self.assertTrue(all(x['match'] for x in self.report['method_bindings']))

    def test_r4_mid_function_byte_address_is_rejected(self):
        profile=json.loads((ROOT/'profiles'/self.report['profile']).read_text())
        profile['native_macros']['RVA_OBSCURED_BYTE']='0x18dab20'
        checks=inspect_method_bindings(self.game.library,profile)
        byte=next(x for x in checks if x['macro']=='RVA_OBSCURED_BYTE')
        self.assertFalse(byte['match'])
        self.assertEqual(byte['actual_method_rva'],'0x18daa20')
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'bad.json').write_text(json.dumps(profile))
            self.assertFalse(inspect_game(self.game,d)['can_build'])

    def test_unrelated_binary_change_blocks_all_features(self):
        game=copy.copy(self.game);game.hashes=dict(game.hashes,libil2cpp_sha256='0'*64)
        report=inspect_game(game)
        self.assertTrue(all(x['match'] for x in report['module_fingerprints']))
        self.assertFalse(report['can_build'])
        self.assertFalse(any(f['compatible'] for f in report['features'].values()))

    def test_same_code_with_unknown_version_stays_blocked(self):
        game=copy.copy(self.game);game.identity=dict(game.identity,version_name='5.2.0',version_code=999)
        self.assertFalse(inspect_game(game)['can_build'])

    def test_resource_change_and_extra_split_block_build(self):
        game=copy.copy(self.game);game.hashes=dict(game.hashes,unity_data_sha256='0'*64)
        self.assertFalse(inspect_game(game)['can_build'])
        game.hashes=self.game.hashes;game.resource_splits=['config.lang.apk']
        self.assertFalse(inspect_game(game)['can_build'])

    def test_draft_cannot_reuse_module_or_enable_features(self):
        with tempfile.TemporaryDirectory() as d:
            path=draft_profile(self.report,Path(d)/'draft.json')
            profile=json.loads(path.read_text())
            self.assertFalse(profile['builder']['verified'])
            self.assertIsNone(profile['builder']['prebuilt_module_sha256'])
            self.assertFalse(any(profile['builder']['features'].values()))
            self.assertFalse(inspect_game(self.game,d)['can_build'])

    def test_untrusted_macro_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):generate_header({'native_macros':{'RVA_BAD\n#error':'0x01'}},Path(d)/'header.h')

    def test_changed_layout_cannot_reuse_prebuilt_binding(self):
        profile=json.loads((ROOT/'profiles'/self.report['profile']).read_text())
        original_binding=native_config_digest(profile)
        # r10 adds camera/UI hooks. The archived r6 module retains its old
        # binding and must be rejected instead of relabelled as an r10 build.
        self.assertNotEqual(profile['builder']['prebuilt_config_sha256'],original_binding)
        profile['native_macros']['FIELD_PLAYERCONTROL_USTATUS']='0x78'
        self.assertNotEqual(native_config_digest(profile),profile['builder']['prebuilt_config_sha256'])

    def test_pack_traversal_is_rejected_before_reading(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'bad.tankpack'
            with zipfile.ZipFile(path,'w') as z:z.writestr('../model.glb',b'')
            with self.assertRaisesRegex(ValueError,'不安全路径'):validate_pack(path)

    def test_neutral_parameter_pack_does_not_claim_injection(self):
        docs={name:json.loads((ROOT/'tanks/template'/(name+'.json')).read_text()) for name in ['manifest','tank','weapon','armor']}
        report=validate_documents(docs);self.assertTrue(report['valid']);self.assertFalse(report['can_inject'])
        docs['weapon']['ammo']['HE']=-1;self.assertFalse(validate_documents(docs)['valid'])

    def test_failed_build_keeps_previous_output_and_writes_report(self):
        with tempfile.TemporaryDirectory() as d:
            output=Path(d)/'prior.apk';output.write_bytes(b'prior output')
            config=Path(d)/'config.json';config.write_text('{}')
            report=run_build(ARGS.apks,output,config,log=lambda x:None)
            self.assertEqual(report['status'],'failed');self.assertEqual(output.read_bytes(),b'prior output')
            self.assertTrue((Path(d)/'build_report.json').is_file())

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--apks',required=True)
    ARGS,remaining=parser.parse_known_args()
    unittest.main(argv=['test_builder']+remaining,verbosity=2)
