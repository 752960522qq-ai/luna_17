"""Read the staged title scene back independently of the builder. No device or APK required."""

import argparse
import struct
import unittest
from pathlib import Path

from tankbuilder.campaign_ugui import (
    BUTTON_TYPE,
    GO_TYPE,
    PTR,
    button_event,
    text_value,
)
from tankbuilder.extra_campaign import (
    BACK,
    BLOCKER,
    EMPTY,
    EMPTY_TEXT,
    ENTRY,
    ENTRY_NAME,
    HOME,
    LABEL,
    LIST,
    ORIGINAL_MENU,
    PAGE_NAME,
    PANEL,
    RAIL,
    SLOT,
    TITLE,
    TITLE_CN,
    Scene,
    file,
    inputs,
    scenes,
)
from tankbuilder.serialization import assert_roundtrip
from tankbuilder.unity_assets import pp


class ExtraCampaign(unittest.TestCase):
    source = staged = None

    @classmethod
    def setUpClass(cls):
        if not cls.source or not cls.staged:
            raise unittest.SkipTest(
                "Pass --source and --scene for release-asset checks"
            )
        cls.stock, cls.stage = scenes(inputs(cls.source))
        cls.ui = Scene(file(cls.staged.read_bytes()), cls.stock.names)
        cls.entry, cls.page = [
            next(p for p, v in cls.ui.go.items() if v["m_Name"] == name)
            for name in [ENTRY_NAME, PAGE_NAME]
        ]

    def child(self, go, name):
        ids = [i for i in self.ui.children(go) if self.ui.go[i]["m_Name"] == name]
        self.assertEqual(len(ids), 1)
        return ids[0]

    def component(self, go, kind, scene=None):
        sc = self.ui if scene is None else scene
        return sc.sf.objects[sc.part[go][kind]].get_raw_data()

    def reference(self, raw, offset, sc):
        fid, pid = PTR.unpack_from(raw, offset)
        self.assertGreater(fid, 0)
        return sc.sf.externals[fid - 1].path, pid

    def test_original_objects_and_menu_order(self):
        self.assertEqual(
            self.ui.children(LIST), [ENTRY, self.entry, *ORIGINAL_MENU[1:]]
        )
        self.assertEqual(
            self.ui.children(PANEL), [HOME, self.page, *self.stock.children(PANEL)[1:]]
        )
        # All original bytes (including campaign mode selection and localization) survive except the
        # two child lists, the six button heights and menu spacing. Check the exact permitted fields.
        expected = {self.ui.rect[g] for g in (LIST, PANEL, *ORIGINAL_MENU)} | {
            self.ui.part[LIST]["VerticalLayoutGroup"]
        }
        changed = {
            p
            for p, o in self.stock.sf.objects.items()
            if self.ui.sf.objects[p].get_raw_data() != o.get_raw_data()
        }
        self.assertEqual(expected, changed)
        for g, extra in [(LIST, self.entry), (PANEL, self.page)]:
            v = self.ui.transform(g)
            v["m_Children"].remove(pp(self.ui.rect[extra]))
            self.assertEqual(v, self.stock.transform(g))
        for g in ORIGINAL_MENU:
            v = self.ui.transform(g)
            self.assertEqual(v["m_SizeDelta"]["y"], 44.0)
            v["m_SizeDelta"]["y"] = 50.0
            self.assertEqual(v, self.stock.transform(g))
        layout = bytearray(self.component(LIST, "VerticalLayoutGroup"))
        self.assertEqual(struct.unpack_from("<f", layout, 52)[0], 4.0)
        struct.pack_into("<f", layout, 52, 5.0)
        self.assertEqual(
            layout, self.component(LIST, "VerticalLayoutGroup", self.stock)
        )
        self.assertEqual(
            button_event(self.component(ENTRY, "Button"))[2][0][2], "ButtonGameMode"
        )

    def test_all_added_objects_have_exactly_one_owner_and_reachable_parent(self):
        all_new = set(self.ui.sf.objects) - set(self.stock.sf.objects)
        reached = set()

        def walk(go, parent):
            self.assertNotIn(go, reached)
            reached.add(go)
            self.assertEqual(
                self.ui.transform(go)["m_Father"], pp(self.ui.rect[parent])
            )
            for c in self.ui.go[go]["m_Component"]:
                pid = c["component"]["m_PathID"]
                self.assertNotIn(pid, reached)
                reached.add(pid)
                obj = self.ui.sf.objects[pid]
                if obj.type.name == "MonoBehaviour":
                    self.assertEqual(PTR.unpack_from(obj.get_raw_data(), 0), (0, go))
                    self.assertNotIn(
                        self.ui.kind(obj), {"LeanLocalizedText", "StageSelectUiManager"}
                    )
                else:
                    self.assertEqual(assert_roundtrip(obj)["m_GameObject"], pp(go))
            for child in self.ui.children(go):
                walk(child, go)

        walk(self.entry, LIST)
        walk(self.page, PANEL)
        self.assertEqual(reached, all_new)

    def test_native_presentation_and_strings(self):
        labels = [
            self.child(self.child(self.entry, n), "Text")
            for n in ["Normal", "Highlighted"]
        ]
        title = self.child(self.child(self.page, "Field Name"), "Text Cn")
        row = self.child(
            self.child(self.page, "Stage Select For Campaign"), "Btn Square (1)"
        )
        status = self.child(row, "Text Coming Soon")
        back = self.child(self.page, "Button Return")
        blocker = self.child(self.page, "Backdrop")
        for g, expected in zip([*labels, title, status], [LABEL, LABEL, TITLE, EMPTY]):
            raw = self.component(g, "Text")
            self.assertEqual(text_value(raw), expected)
            self.assertTrue(raw[12] and self.ui.go[g]["m_IsActive"])
            self.assertEqual(
                self.reference(raw, 88, self.ui), ("sharedassets0.assets", 161)
            )
        for go, source_go in [(title, TITLE_CN), (status, EMPTY_TEXT), (back, BACK)]:
            for kind in ["GradientColor", "Shadow", "Outline"]:
                self.assertEqual(
                    self.component(go, kind)[32:],
                    self.component(source_go, kind, self.stage)[32:],
                )
        for go, source_go in [(row, SLOT), (back, BACK), (blocker, BLOCKER)]:
            self.assertEqual(
                self.reference(self.component(go, "Image"), 88, self.ui),
                self.reference(
                    self.component(source_go, "Image", self.stage), 88, self.stage
                ),
            )
        self.assertNotIn("Button", self.ui.part[row])
        self.assertTrue(self.component(blocker, "Image")[60])
        self.assertEqual(
            self.component(self.child(self.entry, "Background"), "Image")[32:],
            self.component(394, "Image", self.stock)[32:],
        )
        for kind in ["Animator", "AudioSource", "UIElementSound"]:
            self.assertEqual(
                self.component(self.entry, kind)[12:],
                self.component(ENTRY, kind, self.stock)[12:],
            )

    def test_serialized_clicks_switch_visibility_focus_and_return(self):
        active = {g: bool(v["m_IsActive"]) for g, v in self.ui.go.items()}
        parent = {
            go: self.ui.transform(go)["m_Father"]["m_PathID"] for go in self.ui.rect
        }
        inverse = {r: g for g, r in self.ui.rect.items()}
        back = self.child(self.page, "Button Return")
        entry_button, back_button = [
            self.ui.part[g]["Button"] for g in [self.entry, back]
        ]
        selected = None

        def visible(go):
            while True:
                if not active[go]:
                    return False
                if not parent[go]:
                    return True
                go = inverse[parent[go]]

        def click(go):
            nonlocal selected
            self.assertTrue(visible(go))
            raw = self.component(go, "Button")
            target, _, events = button_event(raw)
            self.assertEqual(
                PTR.unpack_from(raw, target), (0, self.ui.part[go]["Image"])
            )
            self.assertTrue(
                self.component(go, "Image")[60] and raw[12] and raw[target - 4]
            )
            self.assertEqual(len(events), 4)
            for (
                fid,
                pid,
            ), cls, method, mode, obj, _, _, _, _, enabled, state in events:
                self.assertEqual((fid, obj, state), (0, (0, 0), 2))
                if method == "SetActive":
                    self.assertEqual((cls, mode), (GO_TYPE, 6))
                    self.assertIn(pid, active)
                    active[pid] = bool(enabled)
                else:
                    self.assertEqual((cls, method, mode), (BUTTON_TYPE, "Select", 1))
                    self.assertIn(pid, (entry_button, back_button))
                    self.assertTrue(
                        visible(self.entry if pid == entry_button else back)
                    )
                    selected = pid

        for _ in range(3):
            self.assertTrue(visible(ENTRY) and visible(self.entry) and visible(RAIL))
            self.assertFalse(visible(self.page))
            click(self.entry)
            self.assertTrue(visible(self.page) and visible(back))
            self.assertFalse(visible(ENTRY) or visible(self.entry) or visible(RAIL))
            self.assertEqual(selected, back_button)
            click(back)
            self.assertTrue(visible(HOME) and visible(self.entry) and visible(RAIL))
            self.assertFalse(visible(self.page) or visible(back))
            self.assertEqual(selected, entry_button)

    def test_stock_scaler_layout_sufficient_at_phone_and_tablet_aspects(self):
        scaler = self.component(194, "CanvasScaler")
        self.assertEqual(
            struct.unpack_from("<ffi", scaler, 44), (960.0, 540.0, 1)
        )  # Expand
        data = self.component(LIST, "VerticalLayoutGroup")
        top, bottom = struct.unpack_from("<ii", data, 40)
        gap = struct.unpack_from("<f", data, 52)[0]
        row_heights = [
            self.ui.transform(g)["m_SizeDelta"]["y"] for g in self.ui.children(LIST)
        ]
        heading = self.child(self.page, "Field Name")
        title = self.ui.transform(self.child(heading, "Text Cn"))
        arrow = self.ui.transform(self.child(self.page, "Button Return"))
        for w, h in [(960, 540), (2400, 1080), (1440, 1080)]:
            scale = min(w / 960, h / 540)
            self.assertLessEqual(
                sum(row_heights) + gap * (len(row_heights) - 1),
                h / scale - top - bottom,
            )
            cy = (
                h / scale
                + self.ui.transform(heading)["m_AnchoredPosition"]["y"]
                + title["m_AnchoredPosition"]["y"]
            )
            self.assertGreater(
                cy - title["m_SizeDelta"]["y"] / 2, h / scale / 2 + 70 + 65 / 2
            )
            self.assertLess(cy + title["m_SizeDelta"]["y"] / 2, h / scale)
            self.assertGreater(
                arrow["m_AnchoredPosition"]["x"] - arrow["m_SizeDelta"]["x"] / 2, 0
            )
            self.assertGreater(
                arrow["m_AnchoredPosition"]["y"] - arrow["m_SizeDelta"]["y"] / 2, 0
            )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--scene", required=True, type=Path)
    args = p.parse_args()
    ExtraCampaign.source, ExtraCampaign.staged = args.source, args.scene
    unittest.main(argv=["test_extra_campaign"], verbosity=2)
