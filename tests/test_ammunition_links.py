import json,unittest
from pathlib import Path
from hatch.ammunition import filling_table,apply_filling_overrides
ROOT=Path(__file__).resolve().parents[1]
class Ammunition(unittest.TestCase):
 def test_every_bundled_vehicle(self):
  table=json.loads((ROOT/'mods/better_tank_experience/features.json').read_text())['ammunition']
  self.assertEqual(len(table),91)
  for vehicle in ['Grille','Matilda_III','Panzer_II_Ausf_L','SU_152','T30','T44_100','T54_1949']:
   w=json.loads((ROOT/'tanks'/vehicle/'weapon.json').read_text());mass=filling_table(w,True)
   for k,v in mass.items():self.assertEqual(v,table[vehicle][k],vehicle+':'+k)
 def test_missing_units_and_zero(self):
  for shell in [{},{'explosiveMassGrams':float('nan')},{'explosiveMassGrams':1,'explosiveMassKg':1}]:
   with self.assertRaises(ValueError):filling_table({'ammo':{'HE':1},'shells':{'HE':shell}},True)
  self.assertEqual(filling_table({'ammo':{'HE':1},'shells':{'HE':{'explosiveMassKg':0}}},True),{'HE':0})
 def test_override_preserves_ballistics(self):
  w={'ammo':{'HE':1},'shells':{'HE':{'penetrationMm':25,'explosiveMassKg':1}},'muzzleVelocity':240}
  new=apply_filling_overrides(w,{'HE':8300});self.assertEqual(new['muzzleVelocity'],240);self.assertEqual(new['shells']['HE']['penetrationMm'],25);self.assertEqual(w['shells']['HE']['explosiveMassKg'],1)
if __name__=='__main__':unittest.main()
