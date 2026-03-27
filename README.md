# test-case-qualia

Coding challenge solution scaffold for Qualia: a Python CLI that augments a LeRobot v3 dataset, uploads it to the Hugging Face Hub, and prints the LeRobot visualizer URL.

## Why this approach

LeRobot v3 is file-based: the tabular data lives in `data/` Parquet shards, while camera frames live in `videos/` MP4 shards and are linked by metadata in `meta/`.

That detail matters. Instead of trying to rebuild episode offsets from scratch, this implementation takes the safer route:

1. Clone the source dataset locally.
2. Rewrite every MP4 shard under `videos/` with deterministic photometric augmentation.
3. Keep the existing Parquet shards and metadata structure intact.
4. Upload the resulting dataset to a new Hugging Face dataset repo.
5. Print a direct visualizer link.

This gives us a useful first augmentation strategy while staying aligned with the actual LeRobot v3 storage model.

## Tech choices

- Python for the core data tooling and CLI
- `huggingface_hub` for download and upload
- `opencv-python-headless` and `numpy` for video augmentation

That keeps the MVP focused on the part of the Qualia stack that matters most for this task: practical Python data tooling.

## Project layout

```text
src/qualia_lerobot_augmentor/
  cli.py           # CLI entrypoint
  config.py        # augmentation presets
  source.py        # source resolution, validation, cloning
  video.py         # MP4 augmentation
  publisher.py     # Hugging Face upload + visualizer URL
  dataset_card.py  # output README + manifest generation
tests/
```

## Install

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
```

## Usage

Local-only run:

```bash
python -m qualia_lerobot_augmentor lerobot/aloha_static_cups_open --skip-upload
```

Upload to the Hub:

```bash
python -m qualia_lerobot_augmentor lerobot/aloha_static_cups_open ^
  --output-dataset-name aloha-static-cups-open-photometric ^
  --preset medium
```

Or via the installed CLI:

```bash
qualia-augment lerobot/aloha_static_cups_open --output-dataset-name aloha-static-cups-open-photometric
```

Authentication uses `HF_TOKEN` or the token already configured for `huggingface_hub`.

If you prefer, you can still pass the full repo id explicitly:

```bash
qualia-augment lerobot/aloha_static_cups_open --output-repo-id your-username/aloha-static-cups-open-photometric
```

## Output

Each run creates:

- a cloned local dataset under `artifacts/`
- rewritten video shards under `videos/`
- `meta/augmentation_manifest.json`
- a generated dataset card at the root `README.md`

When upload is enabled, the tool prints a URL like:

```text
https://huggingface.co/spaces/lerobot/visualize_dataset?path=%2Fyour-username%2Fdataset-name%2Fepisode_0
```

## Current scope

This first version focuses on a safe, interview-friendly augmentation:

- deterministic photometric jitter per video shard
- preserved dataset structure
- automatic Hub publishing

Natural next steps if we want to evolve it into a fuller product:

- multiple augmentation pipelines
- a backend API around the same core package
- a Svelte frontend for run configuration and monitoring
- persisted run history and metadata in Postgres
