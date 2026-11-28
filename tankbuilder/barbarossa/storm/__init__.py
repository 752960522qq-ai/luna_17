"""Stormbreak / 暴风骤雨: second mission on the original Polesie summer terrain."""
from dataclasses import dataclass
from ..mission import Side

TITLE = '暴风骤雨'
PZ2, PZ3, PZ4 = 'Panzer_II_Ausf_F', 'Panzer_III_Ausf_F', 'Panzer_IV_Ausf_C'
RESERVES = {'GE': 312, 'SO': 432}
DEADLINE = 780

@dataclass(frozen=True)
class StormSide(Side):
    @property
    def scene(self):
        return 'Assets/Scenes/ExtraCampaign/Barbarossa_02_Storm_' + self.code + '/Mission_Local_Field_1.unity'
    @property
    def opening(self): return TITLE + '  ·  ' + self.name + '\n' + self.briefing
    @property
    def objective(self): return '全歼苏联守军' if self.code == 'GE' else '守住阵线，击退德军'

SO = StormSide('SO','苏联','防守','BT7','BT-7',24,8832,155866,160402,
               '驾驶 BT-7，守住阵线十三分钟，或提前击退全部德军。')
GE = StormSide('GE','德国','进攻',PZ3,'三号 F 型',25,2676,160403,160403,
               '驾驶三号 F 型，协同两翼，在十三分钟内消灭全部苏联守军。')
SIDES = SO, GE
