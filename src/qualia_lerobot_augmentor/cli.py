from __future__ import annotations

import argparse
import sys
from pathlib import Path

from qualia_lerobot_augmentor.service import RunConfig, default_output_dir as _default_output_dir, run_augmentation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qualia-augment",
        description=(
            "Clone a LeRobot v3 dataset, apply photometric augmentation to its video shards, "
            "and upload the result to the Hugging Face Hub."
        ),
    )
    parser.add_argument(
        "source",
        help="Local path to a LeRobot v3 dataset or a Hugging Face dataset repo id such as lerobot/aloha_static_cups_open.",
    )
    parser.add_argument(
        "--output-repo-id",
        help="Destination dataset repo id on the Hugging Face Hub, for example your-username/aloha-static-cups-open-augmented.",
    )
    parser.add_argument(
        "--output-dataset-name",
        help="Dataset name without the account prefix. The tool will resolve your Hugging Face namespace automatically.",
    )
    parser.add_argument(
        "--namespace",
        help="Optional Hugging Face namespace override used together with --output-dataset-name.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Local directory for the generated dataset. Defaults to artifacts/<repo-name-or-source>.",
    )
    parser.add_argument(
        "--preset",
        default="mild",
        choices=("mild", "medium", "strong"),
        help="Strength of the photometric augmentation.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=7,
        help="Global seed for deterministic video-level transforms.",
    )
    parser.add_argument(
        "--video-codec",
        default="avc1",
        choices=("mp4v", "avc1"),
        help=(
            "Codec used when writing augmented MP4 shards. `avc1` is recommended for browser "
            "playback in the LeRobot visualizer; `mp4v` is a local-only fallback when H.264 "
            "encoding is unavailable."
        ),
    )
    parser.add_argument(
        "--max-videos",
        type=int,
        help="Limit augmentation to the first N discovered MP4 video shards. Useful for quick smoke tests.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(".cache") / "qualia-lerobot-augmentor",
        help="Local cache for Hub downloads.",
    )
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Prepare the augmented dataset locally without uploading it to the Hub.",
    )
    parser.add_argument(
        "--private",
        action="store_true",
        help="Create the destination dataset repo as private.",
    )
    parser.add_argument(
        "--overwrite-output",
        action="store_true",
        help="Replace the output directory if it already exists.",
    )
    parser.add_argument(
        "--episode-index",
        type=int,
        default=0,
        help="Episode index used in the printed visualizer URL.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = run_augmentation(
            RunConfig(
                source=args.source,
                output_repo_id=args.output_repo_id,
                output_dataset_name=args.output_dataset_name,
                namespace=args.namespace,
                output_dir=args.output_dir,
                preset=args.preset,
                seed=args.seed,
                video_codec=args.video_codec,
                max_videos=args.max_videos,
                cache_dir=args.cache_dir,
                skip_upload=args.skip_upload,
                private=args.private,
                overwrite_output=args.overwrite_output,
                episode_index=args.episode_index,
            ),
            progress=_cli_progress,
        )
    except ValueError as exc:
        parser.error(str(exc))
    if args.skip_upload:
        print("Upload skipped.")
    if result.visualizer_url:
        print(result.visualizer_url)
    return 0


def default_output_dir(source_or_repo_id: str) -> Path:
    return _default_output_dir(source_or_repo_id)


def _cli_progress(event: dict[str, object]) -> None:
    message = event.get("message")
    if not isinstance(message, str):
        return

    phase = event.get("phase")
    if phase == "warning":
        print(message, file=sys.stderr)
        return

    print(message, flush=True)
