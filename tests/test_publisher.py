from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qualia_lerobot_augmentor.cli import build_parser, default_output_dir
from qualia_lerobot_augmentor.publisher import build_visualizer_url, resolve_repo_id


class PublisherTests(unittest.TestCase):
    def test_build_visualizer_url_uses_dataset_path_encoding(self) -> None:
        url = build_visualizer_url("alice/my-dataset", episode_index=3)
        self.assertEqual(
            url,
            "https://huggingface.co/spaces/lerobot/visualize_dataset?path=%2Falice%2Fmy-dataset%2Fepisode_3",
        )

    def test_cli_parser_accepts_expected_source_argument(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["lerobot/aloha_static_cups_open", "--skip-upload"])
        self.assertEqual(args.source, "lerobot/aloha_static_cups_open")
        self.assertTrue(args.skip_upload)
        self.assertEqual(args.video_codec, "avc1")

    def test_cli_parser_accepts_max_videos(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["lerobot/aloha_static_cups_open", "--max-videos", "1", "--skip-upload"])
        self.assertEqual(args.max_videos, 1)

    def test_default_output_dir_sanitizes_repo_id(self) -> None:
        output_dir = default_output_dir("alice/my-dataset")
        self.assertEqual(str(output_dir).replace("\\", "/"), "artifacts/alice__my-dataset-photometric")

    def test_resolve_repo_id_prefers_explicit_repo_id(self) -> None:
        repo_id = resolve_repo_id(
            source="lerobot/aloha_static_cups_open",
            output_repo_id="alice/custom-name",
            output_dataset_name=None,
            namespace=None,
            token=None,
        )
        self.assertEqual(repo_id, "alice/custom-name")

    @patch("qualia_lerobot_augmentor.publisher.resolve_namespace", return_value="alice")
    def test_resolve_repo_id_builds_repo_from_account(self, _: object) -> None:
        repo_id = resolve_repo_id(
            source="lerobot/aloha_static_cups_open",
            output_repo_id=None,
            output_dataset_name="aloha-static-cups-open-photometric",
            namespace=None,
            token="hf_test",
        )
        self.assertEqual(repo_id, "alice/aloha-static-cups-open-photometric")


if __name__ == "__main__":
    unittest.main()
