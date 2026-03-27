from __future__ import annotations

from pathlib import Path
from urllib.parse import quote


def build_visualizer_url(repo_id: str, episode_index: int = 0) -> str:
    encoded_path = quote(f"/{repo_id}/episode_{episode_index}", safe="")
    return f"https://huggingface.co/spaces/lerobot/visualize_dataset?path={encoded_path}"


def upload_dataset_folder(
    dataset_dir: Path,
    repo_id: str,
    private: bool,
    token: str | None,
) -> str:
    try:
        from huggingface_hub import HfApi
    except ImportError as exc:
        raise RuntimeError(
            "huggingface_hub is required to upload datasets. Install dependencies with `pip install -e .`."
        ) from exc

    api = HfApi(token=token)
    api.create_repo(repo_id=repo_id, repo_type="dataset", private=private, exist_ok=True)
    api.upload_folder(
        repo_id=repo_id,
        repo_type="dataset",
        folder_path=str(dataset_dir),
        commit_message="Upload augmented LeRobot dataset",
    )
    return build_visualizer_url(repo_id)


def resolve_repo_id(
    source: str,
    output_repo_id: str | None,
    output_dataset_name: str | None,
    namespace: str | None,
    token: str | None,
) -> str | None:
    if output_repo_id:
        return output_repo_id

    if not output_dataset_name:
        return None

    resolved_namespace = namespace or resolve_namespace(token=token)
    return f"{resolved_namespace}/{output_dataset_name}"


def resolve_namespace(token: str | None) -> str:
    try:
        from huggingface_hub import HfApi
    except ImportError as exc:
        raise RuntimeError(
            "huggingface_hub is required to resolve your account namespace. "
            "Install dependencies with `pip install -e .`."
        ) from exc

    api = HfApi(token=token)
    try:
        info = api.whoami()
    except Exception as exc:  # pragma: no cover - depends on external auth state
        raise RuntimeError(
            "Could not determine your Hugging Face account. "
            "Set HF_TOKEN/HUGGINGFACE_HUB_TOKEN or pass --output-repo-id explicitly."
        ) from exc

    name = info.get("name")
    if not isinstance(name, str) or not name.strip():
        raise RuntimeError(
            "Authenticated Hugging Face account did not return a usable username. "
            "Pass --namespace or --output-repo-id explicitly."
        )
    return name.strip()
