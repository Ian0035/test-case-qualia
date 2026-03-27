from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class AugmentationPreset:
    name: str
    brightness_jitter: float
    contrast_jitter: float
    saturation_jitter: float
    hue_jitter: int
    gamma_jitter: float
    noise_std_max: float

    def to_dict(self) -> dict[str, float | int | str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AugmentationRecipe:
    name: str
    label: str
    description: str
    brightness_bias: float = 0.0
    contrast_bias: float = 0.0
    saturation_bias: float = 0.0
    hue_bias: int = 0
    gamma_bias: float = 0.0
    noise_floor: float = 0.0
    blur_probability: float = 0.0
    blur_kernel_min: int = 0
    blur_kernel_max: int = 0
    compression_probability: float = 0.0
    compression_quality_min: int = 0
    compression_quality_max: int = 0

    def to_dict(self) -> dict[str, float | int | str]:
        return asdict(self)


PRESETS: dict[str, AugmentationPreset] = {
    "mild": AugmentationPreset(
        name="mild",
        brightness_jitter=0.10,
        contrast_jitter=0.10,
        saturation_jitter=0.10,
        hue_jitter=4,
        gamma_jitter=0.06,
        noise_std_max=0.01,
    ),
    "medium": AugmentationPreset(
        name="medium",
        brightness_jitter=0.16,
        contrast_jitter=0.15,
        saturation_jitter=0.14,
        hue_jitter=8,
        gamma_jitter=0.10,
        noise_std_max=0.018,
    ),
    "strong": AugmentationPreset(
        name="strong",
        brightness_jitter=0.22,
        contrast_jitter=0.20,
        saturation_jitter=0.20,
        hue_jitter=12,
        gamma_jitter=0.14,
        noise_std_max=0.025,
    ),
}


RECIPES: dict[str, AugmentationRecipe] = {
    "balanced": AugmentationRecipe(
        name="balanced",
        label="Balanced lighting",
        description="General-purpose photometric variation for broader visual diversity without strongly shifting the scene style.",
    ),
    "low_light": AugmentationRecipe(
        name="low_light",
        label="Low light",
        description="Simulates dimmer scenes with darker exposure, extra sensor noise, and softer detail.",
        brightness_bias=-0.16,
        contrast_bias=-0.04,
        saturation_bias=-0.10,
        gamma_bias=0.20,
        noise_floor=0.015,
        blur_probability=0.45,
        blur_kernel_min=3,
        blur_kernel_max=5,
    ),
    "warm_shift": AugmentationRecipe(
        name="warm_shift",
        label="Warm shift",
        description="Introduces warmer, sunlit color balance with a gentle exposure lift.",
        brightness_bias=0.05,
        saturation_bias=0.08,
        hue_bias=10,
    ),
    "cool_shift": AugmentationRecipe(
        name="cool_shift",
        label="Cool shift",
        description="Pushes the image toward cooler tones that resemble overcast or fluorescent lighting.",
        brightness_bias=-0.02,
        saturation_bias=-0.04,
        hue_bias=-10,
    ),
    "sensor_noise": AugmentationRecipe(
        name="sensor_noise",
        label="Sensor noise",
        description="Adds digital sensor roughness and a slightly harsher contrast profile.",
        contrast_bias=0.08,
        saturation_bias=-0.06,
        noise_floor=0.02,
    ),
    "compression": AugmentationRecipe(
        name="compression",
        label="Compression artifacts",
        description="Introduces blur and JPEG-style compression damage similar to low-bandwidth capture pipelines.",
        contrast_bias=0.03,
        saturation_bias=-0.05,
        blur_probability=0.35,
        blur_kernel_min=3,
        blur_kernel_max=5,
        compression_probability=1.0,
        compression_quality_min=26,
        compression_quality_max=48,
    ),
}


def get_preset(name: str) -> AugmentationPreset:
    try:
        return PRESETS[name]
    except KeyError as exc:
        options = ", ".join(sorted(PRESETS))
        raise ValueError(f"Unknown preset '{name}'. Expected one of: {options}.") from exc


def get_recipe(name: str) -> AugmentationRecipe:
    try:
        return RECIPES[name]
    except KeyError as exc:
        options = ", ".join(sorted(RECIPES))
        raise ValueError(f"Unknown recipe '{name}'. Expected one of: {options}.") from exc


def list_recipes() -> list[AugmentationRecipe]:
    return [RECIPES[name] for name in sorted(RECIPES)]
