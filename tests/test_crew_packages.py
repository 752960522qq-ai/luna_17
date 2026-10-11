"""Validate voice mappings and the original uploaded resource archive."""
import hashlib,io,json,tempfile,unittest,zipfile
from pathlib import Path
from hatch.features import pack_features
from hatch.package import validate
ROOT=Path(__file__).resolve().parents[1]
VOICE=ROOT.parent/'upload'/'中系新语音.zip'
class CrewPackages(unittest.TestCase):
    def test_every_default_mapping_exists_and_segment_ranges_complete(self):
        directory=ROOT/'mods/better_crew_experience'
        inventory=json.loads((directory/'voice-inventory.json').read_text())
        config=json.loads((directory/'features.json').read_text())['crew']
        self.assertEqual(len(inventory),641)
        self.assertEqual(config['mode'],'drop-while-speaking')
        for clips in config['events'].values():
            for clip in clips:self.assertIn(clip,inventory)
        for n in range(1,13):self.assertIn(f'voice_message_commander_target_{n}_h.wav',inventory)
        for n in [300,450,900,1000,1500,2000]:self.assertIn(f'voice_message_commander_target_{n}_m.wav',inventory)
        for prefix in ['targetPrefix','distancePrefix']:self.assertIn(config[prefix],inventory)
    @unittest.skipUnless(VOICE.is_file(),'Uploaded WAV archive not available; pass --voice-archive to builder')
    def test_real_archive_checksums_and_pack(self):
        inventory=json.loads((ROOT/'mods/better_crew_experience/voice-inventory.json').read_text())
        with zipfile.ZipFile(VOICE) as archive:
            self.assertEqual(set(archive.namelist()),set(inventory))
            for name,item in inventory.items():
                data=archive.read(name)
                self.assertEqual(len(data),item['bytes']);self.assertEqual(hashlib.sha256(data).hexdigest(),item['sha256'])
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/'crew.hatch'
            pack_features(ROOT/'mods/better_crew_experience',target,VOICE)
            doc=validate(target);self.assertIn('crew-voice-v1',doc['capabilities'])
            with zipfile.ZipFile(target) as archive:
                self.assertEqual(set(archive.namelist()),{'hatch.json','features.json','voices.zip'})
    def test_embedded_voice_path_traversal_and_false_wav_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'extension';source.mkdir()
            base=json.loads((ROOT/'mods/better_crew_experience/hatch.json').read_text())
            for name,data in [('../escape.wav',b'RIFF'+bytes(4)+b'WAVE'+bytes(32)),('clip.wav',bytes(44))]:
                nested=io.BytesIO()
                with zipfile.ZipFile(nested,'w') as archive:archive.writestr(name,data)
                payload=nested.getvalue();voice=source/'voice.zip';voice.write_bytes(payload)
                (source/'hatch.json').write_text(json.dumps(base));(source/'features.json').write_text('{"schema":1,"crew":{}}')
                (source/'audio-source.json').write_text(json.dumps({'sha256':hashlib.sha256(payload).hexdigest()}))
                with self.subTest(name=name),self.assertRaises(ValueError):pack_features(source,Path(temp)/'bad.hatch',voice)
if __name__=='__main__':unittest.main()
