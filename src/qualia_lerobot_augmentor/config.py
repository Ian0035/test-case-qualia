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


def get_preset(name: str) -> AugmentationPreset:
    try:
        return PRESETS[name]
    except KeyError as exc:
        options = ", ".join(sorted(PRESETS))
        raise ValueError(f"Unknown preset '{name}'. Expected one of: {options}.") from exc

