from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qualia_lerobot_augmentor.config import get_recipe, list_recipes
from qualia_lerobot_augmentor.service import _build_variant_plans, _suffix_dataset_name, _suffix_repo_id


class ServiceTests(unittest.TestCase):
    def test_list_recipes_exposes_multiple_named_tools(self) -> None:
        recipe_names = {recipe.name for recipe in list_recipes()}
        self.assertIn("balanced", recipe_names)
        self.assertIn("low_light", recipe_names)
        self.assertIn("compression", recipe_names)

    def test_get_recipe_returns_product_metadata(self) -> None:
        recipe = get_recipe("warm_shift")
        self.assertEqual(recipe.label, "Warm shift")
        self.assertTrue(recipe.description)

    def test_build_variant_plans_keeps_single_run_name_clean(self) -> None:
        plans = _build_variant_plans(recipes=("balanced",), variant_count=1, seed=7)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].suffix, "")
        self.assertEqual(plans[0].seed, 7)

    def test_build_variant_plans_expands_recipe_and_variant_batches(self) -> None:
        plans = _build_variant_plans(recipes=("balanced", "compression"), variant_count=2, seed=11)
        self.assertEqual([plan.suffix for plan in plans], ["balanced-v1", "balanced-v2", "compression-v1", "compression-v2"])
        self.assertEqual([plan.seed for plan in plans], [11, 12, 13, 14])

    def test_suffix_helpers_preserve_single_variant_names(self) -> None:
        self.assertEqual(_suffix_dataset_name("demo", ""), "demo")
        self.assertEqual(_suffix_repo_id("alice/demo", ""), "alice/demo")

    def test_suffix_helpers_append_batch_suffixes(self) -> None:
        self.assertEqual(_suffix_dataset_name("demo", "compression-v1"), "demo-compression-v1")
        self.assertEqual(_suffix_repo_id("alice/demo", "compression-v1"), "alice/demo-compression-v1")


if __name__ == "__main__":
    unittest.main()
