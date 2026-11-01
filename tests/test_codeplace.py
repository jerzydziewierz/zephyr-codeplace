"""python3 -m unittest discover -s tests (from the repository root)."""

import unittest
from pathlib import Path

from codeplace import mapfile, place, profile

D = Path(__file__).with_name("data")
WIN = mapfile.parse_windows("0x10000000-0x11000000")


class Test(unittest.TestCase):
    def setUp(self):
        self.secs = mapfile.sections(D / "tiny.map", WIN)
        self.pcs = profile.load_pcs(D / "tiny.pcs")

    def test_sections(self):
        names = [s.name for s in self.secs]
        self.assertIn(".text.a_very_long_function_name_that_wraps", names)  # name and address on two lines
        self.assertNotIn(".bss.x", names)
        self.assertEqual(mapfile.lib_of(self.secs[0].path), "libfoo")
        self.assertEqual(mapfile.ld_pattern(self.secs[0]), "*libfoo.a:a.c.obj(.text.hot_a)")

    def test_attribute(self):
        per, lines, outside = profile.attribute(self.secs, self.pcs, 8)
        by = {self.secs[i].name: c for i, c in per.items()}
        self.assertEqual(by[".text.hot_a"], 3)
        self.assertEqual(outside, 1)
        self.assertEqual(len(lines[[i for i in per if self.secs[i].name == ".text.hot_a"][0]]), 2)

    def test_pick_and_colour(self):
        w = profile.line_weights(self.secs, [(self.secs, self.pcs)], 8)
        picked, used = place.pick(self.secs, w, 0x60, exclude={".text.idle"})
        self.assertEqual([self.secs[i].name for i in picked][:1], [".text.hot_a"])  # 3 samples in 64 B beats 1 in 32 B
        self.assertLessEqual(used, 0x60)
        cmake = place.zephyr_relocate_cmake(self.secs, picked, "ITCM")
        self.assertIn("LOCATION ITCM_TEXT", cmake)
        cache = place.Cache(sets=16, ways=2, line=8)
        plan, _ = place.colour(self.secs, w, cache)
        placed = place.place(self.secs, plan, cache, 0x10000400)
        for i, a in placed:
            self.assertEqual(a % 8, self.secs[i].addr % 8)
            self.assertEqual((a // 8) % 16, plan[i])


if __name__ == "__main__":
    unittest.main()
