# Qualia LeRobot Augmentor

Local tooling for augmenting a LeRobot v3 dataset, publishing the result to Hugging Face Hub, and opening the dataset in the LeRobot visualizer.

![Qualia LeRobot Augmentor UI](./Screenshot-of-%20application.png)

This project includes:

- a Python CLI for dataset augmentation
- a FastAPI backend for running jobs locally
- a Svelte + Tailwind frontend for launching and monitoring runs

## What It Does

The tool works with the actual LeRobot v3 dataset structure:

- episode tables stay in `data/`
- metadata stays in `meta/`
- camera video shards stay in `videos/`

Instead of rebuilding the whole dataset format, the pipeline:

1. Resolves a source dataset from a local path or Hugging Face repo id.
2. Clones that dataset into a local output folder.
3. Rewrites MP4 shards under `videos/` with deterministic augmentation.
4. Writes an augmentation manifest and dataset card.
5. Uploads the output to Hugging Face Hub.
6. Produces a direct LeRobot visualizer link.

That keeps the dataset layout valid while still giving us a practical augmentation workflow.

## Current Product Shape

Current core features:

- browser-playable H.264 (`avc1`) output by default
- named augmentation tools:
  - `balanced`
  - `low_light`
  - `warm_shift`
  - `cool_shift`
  - `sensor_noise`
  - `compression`
- intensity presets:
  - `mild`
  - `medium`
  - `strong`
- deterministic runs via seed control
- optional smoke testing with only the first `N` videos
- automatic Hugging Face upload
- direct LeRobot visualizer links
- local web UI with live progress and run history


## Requirements

Before setup, make sure you have:

- Python 3.10 or newer
- Node.js 18 or newer
- npm

On Windows, verify these work:

```powershell
python --version
npm --version
node --version
```

If `python` is not found, install Python from python.org and make sure it is added to `PATH`.

## Step-By-Step Setup

These steps assume Windows PowerShell from the project root.

### 1. Clone the repo

```powershell
git clone <your-repo-url>
cd test-case-qualia
```

### 2. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install Python dependencies

Install the backend, CLI, tests, and web dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".[dev,web]"
```


### 4. Configure your Hugging Face token

Uploads require a Hugging Face token with permission to create and upload dataset repos.

The simplest session-only setup is:

```powershell
$env:HF_TOKEN = "hf_your_token_here"
```

Important behavior:

- uploads are performed by the Python backend
- the backend uses the token configured on the machine
- datasets will publish under the Hugging Face account tied to that token

So if your local backend is using your token, all uploads from the UI will go to your account.

If you only want to test locally and do not want to upload yet, you can use the UI or CLI with upload disabled.

## Build the Project

### 1. Build the Backend

From the repo root:

```powershell
.\.venv\Scripts\Activate.ps1
qualia-augment-web
```

Then open:

```text
http://127.0.0.1:8000
```
You can test the status of the Backend by
```text
http://127.0.0.1:8000/api/health
```
### 2. Build the frontend

```powershell

cd frontend
npm install
npm run build
```

Then open:

```text
http://127.0.0.1:5173
```

This is the simplest way to use the app.

## How AI Coding Agents Were Used

This project was built iteratively with heavy AI coding agent support, especially for:

- scaffolding the initial CLI and pipeline structure
- debugging Windows environment and H.264 encoding issues
- switching video writing to FFmpeg-based H.264 output
- adding the FastAPI backend and Svelte frontend

## Current Scope And Next Steps

Current scope:

- one augmentation tool per UI run
- local in-memory run history

Natural next steps:

- multiple augmentation tools per UI run
- persist job history
- host the tool online
- add richer dataset QA and validation reports
- increase speed of processing and augmentation
