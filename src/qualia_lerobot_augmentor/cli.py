from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from qualia_lerobot_augmentor.config import get_preset
from qualia_lerobot_augmentor.dataset_card import write_dataset_card, write_manifest
from qualia_lerobot_augmentor.publisher import (
    build_visualizer_url,
    resolve_repo_id,
    upload_dataset_folder,
)
from qualia_lerobot_augmentor.source import (
    clone_dataset,
    discover_video_files,
    prepare_output_dir,
    resolve_source,
    validate_lerobot_dataset,
)
from qualia_lerobot_augmentor.video import augment_video_file


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
        default="mp4v",
        choices=("mp4v", "avc1"),
        help="Codec used when writing augmented MP4 shards. `mp4v` is the safest default on Windows.",
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

    if args.output_repo_id and args.output_dataset_name:
        parser.error("Use either --output-repo-id or --output-dataset-name, not both.")

    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN")
    resolved_repo_id = resolve_repo_id(
        source=args.source,
        output_repo_id=args.output_repo_id,
        output_dataset_name=args.output_dataset_name,
        namespace=args.namespace,
        token=token,
    )
    if not args.skip_upload and not resolved_repo_id:
        parser.error(
            "Upload requires either --output-repo-id or --output-dataset-name "
            "(optionally with --namespace)."
        )

    preset = get_preset(args.preset)
    source = resolve_source(args.source, cache_dir=args.cache_dir, token=token)

    output_dir = args.output_dir or default_output_dir(resolved_repo_id or args.source)
    output_dir = output_dir.resolve()
    prepare_output_dir(output_dir, overwrite=args.overwrite_output)
    clone_dataset(source.path, output_dir)
    validate_lerobot_dataset(output_dir)

    video_files = discover_video_files(output_dir)
    if not video_files:
        raise RuntimeError(f"No MP4 files were found under {output_dir / 'videos'}")

    summaries = []
    print(f"Cloned dataset into: {output_dir}")
    print(
        f"Processing {len(video_files)} video files with preset '{preset.name}' "
        f"using codec '{args.video_codec}'..."
    )
    for index, video_file in enumerate(video_files, start=1):
        relative_path = str(video_file.relative_to(output_dir)).replace("\\", "/")
        print(f"[{index}/{len(video_files)}] Starting {relative_path}...", flush=True)
        started_at = time.perf_counter()
        summary = augment_video_file(
            video_file,
            preset=preset,
            seed=args.seed,
            seed_key=relative_path,
            codec=args.video_codec,
        )
        summaries.append(summary)
        elapsed_seconds = time.perf_counter() - started_at
        print(
            f"[{index}/{len(video_files)}] Finished {video_file.relative_to(output_dir)} "
            f"- {summary.frame_count} frames at {summary.width}x{summary.height} "
            f"in {elapsed_seconds:.1f}s",
            flush=True,
        )

    write_manifest(
        dataset_dir=output_dir,
        source=source.label,
        output_repo_id=resolved_repo_id,
        preset=preset,
        seed=args.seed,
        summaries=summaries,
    )
    write_dataset_card(
        dataset_dir=output_dir,
        source=source.label,
        output_repo_id=resolved_repo_id,
        preset=preset,
        summaries=summaries,
    )

    if args.skip_upload:
        print("Upload skipped.")
        if resolved_repo_id:
            print(build_visualizer_url(resolved_repo_id, episode_index=args.episode_index))
        return 0

    visualizer_url = upload_dataset_folder(
        dataset_dir=output_dir,
        repo_id=resolved_repo_id,
        private=args.private,
        token=token,
    )
    print(f"Uploaded dataset to: {resolved_repo_id}")
    if args.episode_index != 0:
        visualizer_url = build_visualizer_url(resolved_repo_id, episode_index=args.episode_index)
    print(visualizer_url)
    return 0


def default_output_dir(source_or_repo_id: str) -> Path:
    sanitized = source_or_repo_id.strip().replace("\\", "__").replace("/", "__").replace(":", "")
    return Path("artifacts") / f"{sanitized}-photometric"
