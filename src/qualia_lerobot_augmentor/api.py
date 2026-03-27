from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock, Thread
from typing import Any
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from qualia_lerobot_augmentor.config import list_recipes
from qualia_lerobot_augmentor.service import RunConfig, RunResult, run_augmentation


class RunCreateRequest(BaseModel):
    source: str = Field(default="lerobot/aloha_static_cups_open")
    output_repo_id: str | None = None
    output_dataset_name: str | None = "aloha-static-cups-open-photometric-ui"
    namespace: str | None = None
    output_dir: str | None = None
    preset: str = "strong"
    recipes: list[str] = Field(default_factory=lambda: ["balanced"])
    variant_count: int = 1
    seed: int = 7
    video_codec: str = "avc1"
    max_videos: int | None = 1
    cache_dir: str = str(Path(".cache") / "qualia-lerobot-augmentor")
    skip_upload: bool = False
    private: bool = False
    overwrite_output: bool = True
    episode_index: int = 0


@dataclass(slots=True)
class JobState:
    job_id: str
    created_at: str
    config: dict[str, Any]
    status: str = "queued"
    phase: str = "queued"
    message: str = "Queued"
    logs: list[str] = field(default_factory=list)
    processed_videos: int = 0
    total_videos: int | None = None
    current_video: str | None = None
    completed_variants: int = 0
    total_variants: int | None = None
    current_variant: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "created_at": self.created_at,
            "config": self.config,
            "status": self.status,
            "phase": self.phase,
            "message": self.message,
            "logs": self.logs,
            "processed_videos": self.processed_videos,
            "total_videos": self.total_videos,
            "current_video": self.current_video,
            "completed_variants": self.completed_variants,
            "total_variants": self.total_variants,
            "current_variant": self.current_variant,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "result": self.result,
            "error": self.error,
        }


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}
        self._lock = Lock()

    def create_job(self, request: RunCreateRequest) -> JobState:
        job = JobState(
            job_id=str(uuid4()),
            created_at=_timestamp(),
            config=request.model_dump(),
        )
        with self._lock:
            self._jobs[job.job_id] = job
        thread = Thread(target=self._run_job, args=(job.job_id, request), daemon=True)
        thread.start()
        return job

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            jobs = [job.to_dict() for job in self._jobs.values()]
        jobs.sort(key=lambda item: item["created_at"], reverse=True)
        return jobs

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return None if job is None else job.to_dict()

    def _run_job(self, job_id: str, request: RunCreateRequest) -> None:
        self._update(job_id, status="running", phase="starting", message="Starting run...", started_at=_timestamp())
        try:
            result = run_augmentation(self._to_run_config(request), progress=lambda event: self._on_progress(job_id, event))
        except Exception as exc:
            self._update(
                job_id,
                status="failed",
                phase="failed",
                message=str(exc),
                error=str(exc),
                finished_at=_timestamp(),
            )
            return

        self._update(
            job_id,
            status="completed",
            phase="completed",
            message="Run completed.",
            result=_serialize_result(result),
            finished_at=_timestamp(),
        )

    def _on_progress(self, job_id: str, event: dict[str, object]) -> None:
        updates: dict[str, Any] = {}
        message = event.get("message")
        if isinstance(message, str):
            updates["message"] = message
        phase = event.get("phase")
        if isinstance(phase, str):
            updates["phase"] = phase
        processed_videos = event.get("processed_videos")
        if isinstance(processed_videos, int):
            updates["processed_videos"] = processed_videos
        total_videos = event.get("total_videos")
        if isinstance(total_videos, int):
            updates["total_videos"] = total_videos
        completed_variants = event.get("completed_variants")
        if isinstance(completed_variants, int):
            updates["completed_variants"] = completed_variants
        total_variants = event.get("total_variants")
        if isinstance(total_variants, int):
            updates["total_variants"] = total_variants
        current_video = event.get("current_video")
        if isinstance(current_video, str):
            updates["current_video"] = current_video
        current_variant = event.get("current_variant")
        if isinstance(current_variant, str):
            updates["current_variant"] = current_variant
        visualizer_url = event.get("visualizer_url")
        output_dir = event.get("output_dir")
        variant_results = event.get("variant_results")
        if visualizer_url or output_dir or isinstance(variant_results, list):
            existing = self.get_job(job_id)
            result = {} if existing is None or existing["result"] is None else dict(existing["result"])
            if isinstance(visualizer_url, str):
                result["visualizer_url"] = visualizer_url
            if isinstance(output_dir, str):
                result["output_dir"] = output_dir
            if isinstance(variant_results, list):
                result["variants"] = variant_results
            updates["result"] = result
        self._update(job_id, **updates)

    def _update(self, job_id: str, **updates: Any) -> None:
        with self._lock:
            job = self._jobs[job_id]
            message = updates.get("message")
            if isinstance(message, str):
                job.logs.append(f"[{_timestamp()}] {message}")
                job.logs = job.logs[-250:]
            for key, value in updates.items():
                setattr(job, key, value)

    @staticmethod
    def _to_run_config(request: RunCreateRequest) -> RunConfig:
        output_dir = Path(request.output_dir) if request.output_dir else None
        return RunConfig(
            source=request.source,
            output_repo_id=request.output_repo_id,
            output_dataset_name=request.output_dataset_name,
            namespace=request.namespace,
            output_dir=output_dir,
            preset=request.preset,
            recipes=tuple(request.recipes),
            variant_count=request.variant_count,
            seed=request.seed,
            video_codec=request.video_codec,
            max_videos=request.max_videos,
            cache_dir=Path(request.cache_dir),
            skip_upload=request.skip_upload,
            private=request.private,
            overwrite_output=request.overwrite_output,
            episode_index=request.episode_index,
        )


def create_app() -> FastAPI:
    app = FastAPI(title="Qualia LeRobot Augmentor UI API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    manager = JobManager()

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/options")
    def options() -> dict[str, Any]:
        return {
            "presets": ["mild", "medium", "strong"],
            "recipes": [recipe.to_dict() for recipe in list_recipes()],
            "defaults": RunCreateRequest().model_dump(),
        }

    @app.get("/api/runs")
    def list_runs() -> list[dict[str, Any]]:
        return manager.list_jobs()

    @app.get("/api/runs/{job_id}")
    def get_run(job_id: str) -> dict[str, Any]:
        job = manager.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Run not found.")
        return job

    @app.post("/api/runs", status_code=202)
    def create_run(request: RunCreateRequest) -> dict[str, Any]:
        job = manager.create_job(request)
        return job.to_dict()

    frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

    return app


app = create_app()


def main() -> None:
    uvicorn.run("qualia_lerobot_augmentor.api:app", host="127.0.0.1", port=8000, reload=False)


def _serialize_result(result: RunResult) -> dict[str, Any]:
    return {
        "output_dir": str(result.output_dir) if result.output_dir is not None else None,
        "resolved_repo_id": result.resolved_repo_id,
        "visualizer_url": result.visualizer_url,
        "processed_videos": result.processed_videos,
        "processed_frames": result.processed_frames,
        "source_label": result.source_label,
        "variants": [
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
            for item in result.variants
        ],
    }


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    main()
