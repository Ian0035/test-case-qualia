from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


REQUIRED_PATHS = (
    Path("meta") / "info.json",
    Path("data"),
    Path("videos"),
)


@dataclass(frozen=True, slots=True)
class DatasetSource:
    label: str
    path: Path
    downloaded_from_hub: bool


def validate_lerobot_dataset(dataset_dir: Path) -> None:
    missing = [str(relative_path) for relative_path in REQUIRED_PATHS if not (dataset_dir / relative_path).exists()]
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"{dataset_dir} does not look like a LeRobot v3 dataset. Missing: {missing_text}.")


def resolve_source(source: str, cache_dir: Path, token: str | None) -> DatasetSource:
    candidate = Path(source)
    if candidate.exists():
        dataset_dir = candidate.resolve()
        validate_lerobot_dataset(dataset_dir)
        return DatasetSource(label=str(dataset_dir), path=dataset_dir, downloaded_from_hub=False)

    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError(
            "huggingface_hub is required to download datasets from the Hub. "
            "Install dependencies with `pip install -e .`."
        ) from exc

    download_dir = Path(
        snapshot_download(
            repo_id=source,
            repo_type="dataset",
            token=token,
            cache_dir=str(cache_dir),
        )
    ).resolve()
    validate_lerobot_dataset(download_dir)
    return DatasetSource(label=source, path=download_dir, downloaded_from_hub=True)


def prepare_output_dir(output_dir: Path, overwrite: bool) -> None:
    if output_dir.exists():
        if not overwrite:
            raise FileExistsError(
                f"Output directory already exists: {output_dir}. Use --overwrite-output to replace it."
            )
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def clone_dataset(source_dir: Path, output_dir: Path) -> None:
    if any(output_dir.iterdir()):
        raise ValueError(f"Expected an empty output directory before cloning, but found files in {output_dir}.")

    for item in source_dir.iterdir():
        destination = output_dir / item.name
        if item.is_dir():
            shutil.copytree(item, destination)
        else:
            shutil.copy2(item, destination)


def discover_video_files(dataset_dir: Path) -> list[Path]:
    return sorted(path for path in (dataset_dir / "videos").rglob("*.mp4") if path.is_file())

