from __future__ import annotations

import hashlib
import random
import shutil
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path

from qualia_lerobot_augmentor.config import AugmentationPreset, AugmentationRecipe, get_recipe


@dataclass(frozen=True, slots=True)
class VideoTransform:
    brightness: float
    contrast: float
    saturation: float
    hue_shift: int
    gamma: float
    noise_std: float
    blur_kernel: int
    jpeg_quality: int | None

    def to_dict(self) -> dict[str, float | int | None]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class VideoProcessingSummary:
    path: str
    frame_count: int
    width: int
    height: int
    fps: float
    transform: dict[str, float | int]


class _FFmpegWriter:
    def __init__(self, temp_path: Path, fps: float, width: int, height: int, ffmpeg_exe: str) -> None:
        self.temp_path = temp_path
        self.process = subprocess.Popen(
            _build_ffmpeg_command(
                ffmpeg_exe=ffmpeg_exe,
                temp_path=temp_path,
                fps=fps,
                width=width,
                height=height,
            ),
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

    def write(self, frame) -> None:
        if self.process.stdin is None:
            raise RuntimeError("FFmpeg writer stdin is not available.")
        self.process.stdin.write(frame.tobytes())

    def release(self) -> None:
        stderr_output = ""
        if self.process.stdin is not None:
            self.process.stdin.close()
        if self.process.stderr is not None:
            stderr_output = self.process.stderr.read().decode("utf-8", errors="replace")
            self.process.stderr.close()
        return_code = self.process.wait()
        if return_code != 0:
            self.temp_path.unlink(missing_ok=True)
            detail = stderr_output.strip() or f"ffmpeg exited with status {return_code}"
            raise RuntimeError(f"FFmpeg failed to write H.264 video: {detail}")


def _load_video_stack():
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Video augmentation requires numpy and opencv-python-headless. "
            "Install dependencies with `pip install -e .`."
        ) from exc
    return cv2, np


def stable_seed(seed: int, value: str) -> int:
    digest = hashlib.sha256(f"{seed}:{value}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def sample_transform(recipe: AugmentationRecipe, preset: AugmentationPreset, seed: int) -> VideoTransform:
    rng = random.Random(seed)
    blur_kernel = 0
    if recipe.blur_probability > 0.0 and rng.random() < recipe.blur_probability:
        kernels = [value for value in range(recipe.blur_kernel_min, recipe.blur_kernel_max + 1) if value >= 3 and value % 2 == 1]
        if kernels:
            blur_kernel = rng.choice(kernels)

    jpeg_quality = None
    if recipe.compression_probability > 0.0 and rng.random() < recipe.compression_probability:
        jpeg_quality = rng.randint(recipe.compression_quality_min, recipe.compression_quality_max)

    return VideoTransform(
        brightness=_clamp(1.0 + recipe.brightness_bias + rng.uniform(-preset.brightness_jitter, preset.brightness_jitter), 0.45, 1.6),
        contrast=_clamp(1.0 + recipe.contrast_bias + rng.uniform(-preset.contrast_jitter, preset.contrast_jitter), 0.55, 1.7),
        saturation=_clamp(1.0 + recipe.saturation_bias + rng.uniform(-preset.saturation_jitter, preset.saturation_jitter), 0.4, 1.8),
        hue_shift=recipe.hue_bias + rng.randint(-preset.hue_jitter, preset.hue_jitter),
        gamma=_clamp(1.0 + recipe.gamma_bias + rng.uniform(-preset.gamma_jitter, preset.gamma_jitter), 0.55, 1.8),
        noise_std=max(0.0, recipe.noise_floor + rng.uniform(0.0, preset.noise_std_max)),
        blur_kernel=blur_kernel,
        jpeg_quality=jpeg_quality,
    )


def augment_video_file(
    video_path: Path,
    preset: AugmentationPreset,
    recipe: AugmentationRecipe | None,
    seed: int,
    seed_key: str | None = None,
    codec: str = "avc1",
) -> VideoProcessingSummary:
    cv2, np = _load_video_stack()

    file_seed = stable_seed(seed, seed_key or str(video_path))
    noise_rng = np.random.default_rng(file_seed)
    transform = sample_transform(recipe or get_recipe("balanced"), preset, file_seed)

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Unable to open video for reading: {video_path}")

    fps = float(capture.get(cv2.CAP_PROP_FPS) or 30.0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if width <= 0 or height <= 0:
        capture.release()
        raise RuntimeError(f"Could not determine video dimensions for {video_path}")

    temp_path = video_path.with_suffix(".augmented.tmp.mp4")
    writer = _open_writer(temp_path, fps=fps, width=width, height=height, codec=codec)

    frame_count = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            augmented = _apply_transform(
                frame=frame,
                transform=transform,
                noise_rng=noise_rng,
                cv2=cv2,
                np=np,
            )
            writer.write(augmented)
            frame_count += 1
    finally:
        capture.release()
        writer.release()

    if frame_count == 0:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(f"No frames were read from {video_path}")

    temp_path.replace(video_path)
    return VideoProcessingSummary(
        path=str(video_path),
        frame_count=frame_count,
        width=width,
        height=height,
        fps=fps,
        transform=transform.to_dict(),
    )


def _open_writer(temp_path: Path, fps: float, width: int, height: int, codec: str):
    if codec == "avc1":
        ffmpeg_exe = _find_ffmpeg_executable()
        if ffmpeg_exe:
            return _FFmpegWriter(
                temp_path=temp_path,
                fps=fps,
                width=width,
                height=height,
                ffmpeg_exe=ffmpeg_exe,
            )

    cv2, _ = _load_video_stack()
    writer = cv2.VideoWriter(
        str(temp_path),
        cv2.VideoWriter_fourcc(*codec),
        fps,
        (width, height),
    )
    if writer.isOpened():
        return writer

    writer.release()
    temp_path.unlink(missing_ok=True)
    if codec == "avc1":
        raise RuntimeError(
            f"Unable to open an MP4 video writer for {temp_path} with codec 'avc1'. "
            "The LeRobot visualizer expects browser-playable H.264 video, but this environment "
            "does not currently have a working H.264 encoder. Install `imageio-ffmpeg` or a "
            "`ffmpeg` binary with libx264 support, or use '--video-codec mp4v --skip-upload' "
            "for local-only output."
        )
    raise RuntimeError(
        f"Unable to open an MP4 video writer for {temp_path} with codec '{codec}'. "
        "Try '--video-codec avc1' for browser-playable uploads, or '--video-codec mp4v' for local-only output."
    )


def _find_ffmpeg_executable() -> str | None:
    try:
        import imageio_ffmpeg
    except ImportError:
        return shutil.which("ffmpeg")
    return imageio_ffmpeg.get_ffmpeg_exe()


def _build_ffmpeg_command(
    ffmpeg_exe: str,
    temp_path: Path,
    fps: float,
    width: int,
    height: int,
) -> list[str]:
    return [
        ffmpeg_exe,
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s:v",
        f"{width}x{height}",
        "-r",
        f"{fps:.6f}",
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(temp_path),
    ]


def _apply_transform(frame, transform: VideoTransform, noise_rng, cv2, np):
    frame_f32 = frame.astype(np.float32) / 255.0

    channel_mean = frame_f32.mean(axis=(0, 1), keepdims=True)
    frame_f32 = (frame_f32 - channel_mean) * transform.contrast + channel_mean
    frame_f32 = frame_f32 * transform.brightness
    frame_f32 = np.clip(frame_f32, 0.0, 1.0)

    hsv = cv2.cvtColor((frame_f32 * 255.0).astype(np.uint8), cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] *= transform.saturation
    hsv[:, :, 0] = (hsv[:, :, 0] + transform.hue_shift) % 180.0
    hsv[:, :, 1] = np.clip(hsv[:, :, 1], 0.0, 255.0)
    frame_f32 = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32) / 255.0

    if transform.gamma != 1.0:
        frame_f32 = np.power(np.clip(frame_f32, 0.0, 1.0), transform.gamma)

    if transform.noise_std > 0.0:
        frame_f32 += noise_rng.normal(0.0, transform.noise_std, frame_f32.shape).astype(np.float32)

    frame_f32 = np.clip(frame_f32, 0.0, 1.0)
    frame_u8 = (frame_f32 * 255.0).astype(np.uint8)

    if transform.blur_kernel >= 3:
        frame_u8 = cv2.GaussianBlur(frame_u8, (transform.blur_kernel, transform.blur_kernel), 0)

    if transform.jpeg_quality is not None:
        ok, encoded = cv2.imencode(".jpg", frame_u8, [int(cv2.IMWRITE_JPEG_QUALITY), int(transform.jpeg_quality)])
        if ok:
            decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
            if decoded is not None:
                frame_u8 = decoded

    return frame_u8


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
