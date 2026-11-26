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
from palace_ensemble import ensemble_plan


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

    def test_time_presets_preserve_base_and_add_real_geometry(self):
        drafts = [recipe_roundtrip(search_hall(
            prompt="Пышный зал, ветви аканта и свободные углы потолка",
            seed=724031, backend="rules", size_m=SIZE_M, budget=limit
        )) for limit in (60, 600, 3600)]
        fast, middle, long = drafts
        self.assertNotIn("refinement", fast)
        for plan in (middle, long):
            for key in ("seed", "architecture", "layout", "paintings", "wall_bays"):
                self.assertEqual(plan[key], fast[key])
        middle_layers, long_layers = [plan["refinement"]["stages"] for plan in (middle, long)]
        self.assertEqual(len(middle_layers), 3)
        self.assertEqual(len(long_layers), 6)
        self.assertEqual(middle_layers, {key: long_layers[key] for key in middle_layers})
        rooms = [build_palace(plan, (8000, 6500, 4600), detail=2, painting=plan["paintings"]) for plan in drafts]
        for before, after in zip(rooms, rooms[1:]):
            self.assertLess(len(before.parts), len(after.parts))
            self.assertTrue(all(geometry == after.parts[key] for key, geometry in before.parts.items()))
        self.assertTrue(any("Скульптурная консоль" in zone for zone, _ in rooms[1].parts))
        self.assertTrue(any("Боковая скульптурная группа" in zone for zone, _ in rooms[2].parts))

    def test_deep_local_edit_stays_inside_its_zone(self):
        edited = recipe_roundtrip(edit_hall_zone(
            self.base, "portal", PORTAL_BRIEF, seed=93, budget=3600, backend="rules", size_m=SIZE_M
        ))
        self.assertEqual(set(edited["zones"]["portal"]["refinement"]["stages"]), {"portal", "portal_extra"})
        before, after = mesh(self.base), mesh(edited)
        self.assertEqual({k: v for k, v in before.parts.items() if k[0] != CROWN},
                         {k: v for k, v in after.parts.items() if k[0] != CROWN})

    def test_ensemble_rebuilds_the_architecture_and_roundtrips(self):
        base = dict(self.base, prompt="Сделай парные колонны. Оставь углы потолка пустыми.")
        spec = {"family":"axial","wings":4,"bays":4,"volutes":12,"reach":.60,
                "crown":.47,"drop":.17,"relief":.83,"branch":.80}
        plan = recipe_roundtrip(ensemble_plan(base, spec))
        self.assertEqual(plan["architecture"]["walls"], "pilasters")
        self.assertEqual(plan["wall_bays"], 4)
        self.assertEqual(plan["ensemble"], spec)
        self.assertEqual(len(plan["layout"]), 5)
        _palace_check_intent(plan, base["prompt"])
        model = mesh(plan)
        self.assertTrue(any(zone=="Плафон · Пространственная резная рама" for zone, _ in model.parts))
        self.assertEqual(model.parts[("Паркет","walnut")], mesh(base).parts[("Паркет","walnut")])

    def test_ensemble_search_is_a_separate_budget(self):
        reports = []
        plan = search_hall(seed=2026, backend="rules", size_m=SIZE_M, budget=3600,
                           ensemble_seconds=1, checkpoint=reports.append)
        self.assertEqual(plan["search"]["ensemble_budget_s"], 1)
        self.assertGreaterEqual(plan["search"]["elapsed_s"], 1)
        self.assertGreater(plan["search"]["ensemble_valid"], 1)
        self.assertEqual(plan["search"]["stop"], "ensemble_complete")
        self.assertIn("ensemble", reports[-1])


if __name__ == "__main__":
    unittest.main()
