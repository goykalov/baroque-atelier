import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "atelier"))
from palace_free import read_recipe
from palace_plan import _palace_check_intent
from palace_room import build_palace
from palace_search import edit_hall_zone, hall_history_item, search_hall


SIZE_M = (8, 6.5, 4.6)
CORNER_BRIEF = "Оставь углы потолка пустыми. В центре сделай лучистую розетку."
PORTAL_BRIEF = "Над дверью сделай лёгкую лепнину с раковиной и завитками."
CROWN = "Портал · лепнина над дверью"


def recipe_roundtrip(plan):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "hall.json"
        path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf8")
        return read_recipe(path)


def mesh(plan):
    ceiling = plan.get("zones", {}).get("ceiling", plan)
    return build_palace(plan, tuple(value * 1000 for value in SIZE_M), detail=1, painting=ceiling["paintings"])


class GenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = recipe_roundtrip(search_hall(seed=2026, backend="rules", size_m=SIZE_M))

    def test_ceiling_edit_preserves_all_wall_and_floor_buffers(self):
        revised = recipe_roundtrip(edit_hall_zone(
            self.base, "ceiling", CORNER_BRIEF, seed=41, backend="rules", size_m=SIZE_M
        ))
        _palace_check_intent(revised["zones"]["ceiling"], CORNER_BRIEF)
        before, after = mesh(self.base), mesh(revised)
        def is_ceiling(key):
            return key[0].startswith(("Плафон", "Потолок"))
        self.assertEqual({k: v for k, v in before.parts.items() if not is_ceiling(k)},
                         {k: v for k, v in after.parts.items() if not is_ceiling(k)})
        self.assertNotEqual({k: v for k, v in before.parts.items() if is_ceiling(k)},
                            {k: v for k, v in after.parts.items() if is_ceiling(k)})

    def test_portal_edit_keeps_an_existing_ceiling_revision(self):
        ceiling = edit_hall_zone(self.base, "ceiling", CORNER_BRIEF, seed=41, backend="rules", size_m=SIZE_M)
        revised = recipe_roundtrip(edit_hall_zone(
            ceiling, "portal", PORTAL_BRIEF, seed=93, backend="rules", size_m=SIZE_M
        ))
        self.assertEqual(revised["zones"]["portal"]["motif"], "shell")
        before, after = mesh(ceiling), mesh(revised)
        self.assertEqual({k: v for k, v in before.parts.items() if k[0] != CROWN},
                         {k: v for k, v in after.parts.items() if k[0] != CROWN})
        self.assertNotEqual({k: v for k, v in before.parts.items() if k[0] == CROWN},
                            {k: v for k, v in after.parts.items() if k[0] == CROWN})

    def test_new_halls_change_structural_composition(self):
        history = []
        signatures = set()
        for seed in range(5):
            plan = search_hall(seed=seed, backend="rules", size_m=SIZE_M, history=history)
            arch = plan["architecture"]
            signatures.add((arch["walls"], arch["ceiling"], arch["section"], plan["wall_bays"]))
            history.append(hall_history_item(plan))
        self.assertEqual(len(signatures), 5)
        self.assertGreaterEqual(len({signature[0] for signature in signatures}), 3)

    def test_hour_preset_can_finish_with_first_valid_checkpoint(self):
        saved = []
        plan = search_hall(budget=3600, seed=99, backend="rules", size_m=SIZE_M,
                           checkpoint=saved.append, finish=lambda: bool(saved))
        self.assertEqual(saved[0]["search"]["stop"], "in_progress")
        self.assertEqual(plan["search"]["stop"], "accepted_early")
        self.assertEqual(plan["seed"], saved[0]["seed"])
        self.assertEqual(plan["search"]["valid_recipes"], 1)


if __name__ == "__main__":
    unittest.main()
