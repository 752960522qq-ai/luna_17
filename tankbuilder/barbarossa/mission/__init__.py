"""First Barbarossa battle: one village, two playable sides."""

from dataclasses import dataclass

TITLE = "炼狱之门"
OBJECTIVE_XZ = (-180, -54)


@dataclass(frozen=True)
class Side:
    code: str
    name: str
    action: str
    vehicle: str
    display: str
    index: int
    scenario: int
    objective_control: int
    template_control: int
    briefing: str

    @property
    def nation(self):
        return {"SO": 0, "GE": 1}[self.code]

    @property
    def scene(self):
        # Keep the original Soviet extra scene's full path and the stock field basename.
        sub = "Barbarossa_01_GatesOfHell" + ("_GE" if self.code == "GE" else "")
        return "Assets/Scenes/ExtraCampaign/" + sub + "/Mission_Local_Field_1.unity"

    @property
    def member(self):
        return f"level{self.index}"

    @property
    def label(self):
        return self.name + " · " + self.action + "\n" + self.display

    @property
    def objective(self):
        return ("守住" if self.code == "SO" else "夺取") + "村口阵地"

    @property
    def opening(self):
        return TITLE + "  ·  " + self.name + "\n" + self.briefing

    @property
    def player_id(self):
        return self.code + "_" + self.vehicle + "_01"


SOVIET = Side(
    "SO",
    "苏联",
    "防守",
    "T26",
    "T26",
    22,
    8832,
    155866,
    160402,
    "驾驶 T26，守住村口阵地，消灭来袭德军。",
)
GERMAN = Side(
    "GE",
    "德国",
    "进攻",
    "Panzer_II_Ausf_F",
    "二号 F 型",
    23,
    2676,
    160403,
    160403,
    "驾驶二号 F 型，与友军一同夺取村口阵地。",
)
SIDES = (SOVIET, GERMAN)  # build slot order; menu can arrange controls independently
