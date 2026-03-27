from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from qualia_lerobot_augmentor.config import get_preset, get_recipe
from qualia_lerobot_augmentor.dataset_card import write_dataset_card, write_manifest
from qualia_lerobot_augmentor.publisher import (
    build_visualizer_url,
    resolve_repo_id,
    upload_dataset_folder,
)
from qualia_lerobot_augmentor.source import (
    DatasetSource,
    clone_dataset,
    discover_video_files,
    prepare_output_dir,
    resolve_source,
    validate_lerobot_dataset,
)
from qualia_lerobot_augmentor.video import augment_video_file

ProgressCallback = Callable[[dict[str, object]], None]


@dataclass(frozen=True, slots=True)
class RunConfig:
    source: str
    output_repo_id: str | None = None
    output_dataset_name: str | None = None
    namespace: str | None = None
    output_dir: Path | None = None
    preset: str = "mild"
    recipes: tuple[str, ...] = ("balanced",)
    variant_count: int = 1
    seed: int = 7
    video_codec: str = "avc1"
    max_videos: int | None = None
    cache_dir: Path = Path(".cache") / "qualia-lerobot-augmentor"
    skip_upload: bool = False
    private: bool = False
    overwrite_output: bool = False
    episode_index: int = 0


@dataclass(frozen=True, slots=True)
class VariantRunResult:
    label: str
    recipe_name: str
    recipe_label: str
    variant_index: int
    seed: int
    output_dir: Path
    resolved_repo_id: str | None
    visualizer_url: str | None
    processed_videos: int
    processed_frames: int


@dataclass(frozen=True, slots=True)
class RunResult:
    output_dir: Path | None
    resolved_repo_id: str | None
    visualizer_url: str | None
    processed_videos: int
    processed_frames: int
    source_label: str
    variants: list[VariantRunResult]


@dataclass(frozen=True, slots=True)
class _VariantPlan:
    recipe_name: str
    recipe_label: str
    variant_index: int
    seed: int
    suffix: str
    label: str


def default_output_dir(source_or_repo_id: str) -> Path:
    sanitized = source_or_repo_id.strip().replace("\\", "__").replace("/", "__").replace(":", "")
    return Path("artifacts") / f"{sanitized}-photometric"


def run_augmentation(config: RunConfig, progress: ProgressCallback | None = None) -> RunResult:
    recipes = tuple(config.recipes or ("balanced",))
    if config.max_videos is not None and config.max_videos < 1:
        raise ValueError("--max-videos must be at least 1.")
    if config.variant_count < 1:
        raise ValueError("--variant-count must be at least 1.")
    if config.output_repo_id and config.output_dataset_name:
        raise ValueError("Use either --output-repo-id or --output-dataset-name, not both.")

    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN")
    if not config.skip_upload and not config.output_repo_id and not config.output_dataset_name:
        raise ValueError(
            "Upload requires either --output-repo-id or --output-dataset-name "
            "(optionally with --namespace)."
        )
    if not config.skip_upload and config.video_codec == "mp4v":
        _emit(
            progress,
            phase="warning",
            message=(
                "Codec 'mp4v' often does not play in browser-based viewers such as the "
                "LeRobot visualizer. Prefer 'avc1' for uploaded datasets."
            ),
        )

    preset = get_preset(config.preset)
    plans = _build_variant_plans(recipes=recipes, variant_count=config.variant_count, seed=config.seed)
    _emit(
        progress,
        phase="batch_planned",
        message=f"Prepared {len(plans)} dataset run(s) from {len(recipes)} recipe(s).",
        total_variants=len(plans),
        completed_variants=0,
    )

    _emit(progress, phase="resolving_source", message=f"Resolving source dataset '{config.source}'...")
    source = resolve_source(config.source, cache_dir=config.cache_dir, token=token)

    results: list[VariantRunResult] = []
    for plan_index, plan in enumerate(plans, start=1):
        _emit(
            progress,
            phase="variant_started",
            message=f"Starting batch item {plan_index}/{len(plans)}: {plan.label}.",
            total_variants=len(plans),
            completed_variants=plan_index - 1,
            current_variant=plan.label,
        )
        result = _run_single_variant(
            source=source,
            config=config,
            preset_name=config.preset,
            plan=plan,
            token=token,
            progress=progress,
            variant_position=plan_index,
            total_variants=len(plans),
        )
        results.append(result)
        _emit(
            progress,
            phase="variant_completed",
            message=f"Completed batch item {plan_index}/{len(plans)}: {plan.label}.",
            total_variants=len(plans),
            completed_variants=plan_index,
            current_variant=plan.label,
            variant_results=_serialize_variant_results(results),
        )

    primary = results[0] if len(results) == 1 else None
    return RunResult(
        output_dir=primary.output_dir if primary else None,
        resolved_repo_id=primary.resolved_repo_id if primary else None,
        visualizer_url=primary.visualizer_url if primary else None,
        processed_videos=sum(item.processed_videos for item in results),
        processed_frames=sum(item.processed_frames for item in results),
        source_label=source.label,
        variants=results,
    )


def _run_single_variant(
    source: DatasetSource,
    config: RunConfig,
    preset_name: str,
    plan: _VariantPlan,
    token: str | None,
    progress: ProgressCallback | None,
    variant_position: int,
    total_variants: int,
) -> VariantRunResult:
    preset = get_preset(preset_name)
    recipe = get_recipe(plan.recipe_name)
    output_dataset_name = _suffix_dataset_name(config.output_dataset_name, plan.suffix)
    output_repo_id = _suffix_repo_id(config.output_repo_id, plan.suffix)
    resolved_repo_id = resolve_repo_id(
        source=config.source,
        output_repo_id=output_repo_id,
        output_dataset_name=output_dataset_name,
        namespace=config.namespace,
        token=token,
    )

    output_dir = _resolve_variant_output_dir(config, resolved_repo_id or config.source, plan.suffix)
    _emit(
        progress,
        phase="preparing_output",
        message=f"[{plan.label}] Preparing output directory at {output_dir}...",
        current_variant=plan.label,
        total_variants=total_variants,
        completed_variants=variant_position - 1,
    )
    prepare_output_dir(output_dir, overwrite=config.overwrite_output)

    _emit(
        progress,
        phase="cloning_dataset",
        message=f"[{plan.label}] Cloning dataset into {output_dir}...",
        current_variant=plan.label,
    )
    clone_dataset(source.path, output_dir)
    validate_lerobot_dataset(output_dir)

    video_files = discover_video_files(output_dir)
    if not video_files:
        raise RuntimeError(f"No MP4 files were found under {output_dir / 'videos'}")
    if config.max_videos is not None:
        video_files = video_files[: config.max_videos]
        _emit(
            progress,
            phase="limiting_videos",
            message=f"[{plan.label}] Limiting augmentation to {len(video_files)} video file(s).",
            total_videos=len(video_files),
            current_variant=plan.label,
        )

    summaries = []
    _emit(
        progress,
        phase="processing_started",
        message=(
            f"[{plan.label}] Processing {len(video_files)} video file(s) with recipe '{recipe.label}' "
            f"and intensity '{preset.name}'."
        ),
        total_videos=len(video_files),
        processed_videos=0,
        current_variant=plan.label,
    )
    for index, video_file in enumerate(video_files, start=1):
        relative_path = str(video_file.relative_to(output_dir)).replace("\\", "/")
        _emit(
            progress,
            phase="video_started",
            message=f"[{plan.label}] [{index}/{len(video_files)}] Starting {relative_path}...",
            current_video=relative_path,
            current_variant=plan.label,
            total_videos=len(video_files),
            processed_videos=index - 1,
        )
        started_at = time.perf_counter()
        summary = augment_video_file(
            video_file,
            preset=preset,
            recipe=recipe,
            seed=plan.seed,
            seed_key=relative_path,
            codec=config.video_codec,
        )
        summaries.append(summary)
        elapsed_seconds = time.perf_counter() - started_at
        _emit(
            progress,
            phase="video_finished",
            message=(
                f"[{plan.label}] [{index}/{len(video_files)}] Finished {relative_path} - "
                f"{summary.frame_count} frames at {summary.width}x{summary.height} "
                f"in {elapsed_seconds:.1f}s"
            ),
            current_video=relative_path,
            current_variant=plan.label,
            total_videos=len(video_files),
            processed_videos=index,
        )

    write_manifest(
        dataset_dir=output_dir,
        source=source.label,
        output_repo_id=resolved_repo_id,
        recipe=recipe,
        preset=preset,
        seed=plan.seed,
        summaries=summaries,
    )
    write_dataset_card(
        dataset_dir=output_dir,
        source=source.label,
        output_repo_id=resolved_repo_id,
        recipe=recipe,
        preset=preset,
        summaries=summaries,
    )
    _emit(
        progress,
        phase="finalizing",
        message=f"[{plan.label}] Wrote augmentation manifest and dataset card.",
        processed_videos=len(summaries),
        total_videos=len(video_files),
        current_variant=plan.label,
    )

    visualizer_url = None
    if config.skip_upload:
        if resolved_repo_id:
            visualizer_url = build_visualizer_url(resolved_repo_id, episode_index=config.episode_index)
        _emit(
            progress,
            phase="variant_ready",
            message=f"[{plan.label}] Completed locally without upload.",
            output_dir=str(output_dir),
            visualizer_url=visualizer_url,
            current_variant=plan.label,
            processed_videos=len(summaries),
            total_videos=len(video_files),
        )
    else:
        _emit(
            progress,
            phase="uploading",
            message=f"[{plan.label}] Uploading dataset to {resolved_repo_id}...",
            processed_videos=len(summaries),
            total_videos=len(video_files),
            current_variant=plan.label,
        )
        visualizer_url = upload_dataset_folder(
            dataset_dir=output_dir,
            repo_id=resolved_repo_id,
            private=config.private,
            token=token,
        )
        if config.episode_index != 0:
            visualizer_url = build_visualizer_url(resolved_repo_id, episode_index=config.episode_index)
        _emit(
            progress,
            phase="variant_ready",
            message=f"[{plan.label}] Uploaded dataset to {resolved_repo_id}.",
            visualizer_url=visualizer_url,
            output_dir=str(output_dir),
            current_variant=plan.label,
            processed_videos=len(summaries),
            total_videos=len(video_files),
        )

    return VariantRunResult(
        label=plan.label,
        recipe_name=plan.recipe_name,
        recipe_label=plan.recipe_label,
        variant_index=plan.variant_index,
        seed=plan.seed,
        output_dir=output_dir,
        resolved_repo_id=resolved_repo_id,
        visualizer_url=visualizer_url,
        processed_videos=len(summaries),
        processed_frames=sum(item.frame_count for item in summaries),
    )


def _build_variant_plans(recipes: tuple[str, ...], variant_count: int, seed: int) -> list[_VariantPlan]:
    plans: list[_VariantPlan] = []
    sequence = 0
    single_run = len(recipes) == 1 and variant_count == 1
    for recipe_name in recipes:
        recipe = get_recipe(recipe_name)
        for variant_index in range(variant_count):
            sequence += 1
            suffix = "" if single_run else recipe_name if variant_count == 1 else f"{recipe_name}-v{variant_index + 1}"
            label = recipe.label if variant_count == 1 else f"{recipe.label} · Variant {variant_index + 1}"
            plans.append(
                _VariantPlan(
                    recipe_name=recipe_name,
                    recipe_label=recipe.label,
                    variant_index=variant_index + 1,
                    seed=seed + sequence - 1,
                    suffix=suffix,
                    label=label,
                )
            )
    return plans


def _suffix_dataset_name(dataset_name: str | None, suffix: str) -> str | None:
    if not dataset_name:
        return None
    if not suffix:
        return dataset_name
    return f"{dataset_name}-{suffix}"


def _suffix_repo_id(repo_id: str | None, suffix: str) -> str | None:
    if not repo_id:
        return None
    if not suffix:
        return repo_id
    namespace, _, name = repo_id.partition("/")
    if not name:
        return f"{repo_id}-{suffix}"
    return f"{namespace}/{name}-{suffix}"


def _resolve_variant_output_dir(config: RunConfig, source_or_repo_id: str, suffix: str) -> Path:
    if config.output_dir is not None:
        if config.variant_count == 1 and len(config.recipes) == 1:
            return config.output_dir.resolve()
        return (config.output_dir / suffix).resolve()

    if config.variant_count == 1 and len(config.recipes) == 1:
        return default_output_dir(source_or_repo_id).resolve()
    return default_output_dir(f"{source_or_repo_id}-{suffix}").resolve()


def _serialize_variant_results(results: list[VariantRunResult]) -> list[dict[str, object]]:
    return [
        {
            "label": item.label,
            "recipe_name": item.recipe_name,
            "recipe_label": item.recipe_label,
            "variant_index": item.variant_index,
            "seed": item.seed,
            "output_dir": str(item.output_dir),
            "resolved_repo_id": item.resolved_repo_id,
            "visualizer_url": item.visualizer_url,
            "processed_videos": item.processed_videos,
            "processed_frames": item.processed_frames,
        }
        for item in results
    ]


def _emit(progress: ProgressCallback | None, **event: object) -> None:
    if progress is not None:
        progress(event)
