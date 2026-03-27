<script>
  import { onMount } from 'svelte';
  import Tooltip from './components/Tooltip.svelte';

  const initialForm = {
    source: 'lerobot/aloha_static_cups_open',
    output_dataset_name: 'aloha-static-cups-open-photometric-ui',
    preset: 'strong',
    recipes: ['balanced'],
    variant_count: 1,
    seed: 7,
    max_videos: 1,
    skip_upload: false,
    overwrite_output: true
  };

  const fallbackRecipes = [
    {
      name: 'balanced',
      label: 'Balanced lighting',
      description: 'General-purpose visual variation for broader dataset diversity without strongly shifting the overall look.'
    },
    {
      name: 'compression',
      label: 'Compression artifacts',
      description: 'Adds blur and codec-like compression damage similar to low-bandwidth camera pipelines.'
    },
    {
      name: 'cool_shift',
      label: 'Cool shift',
      description: 'Pushes the image toward cooler tones, similar to overcast or fluorescent lighting.'
    },
    {
      name: 'low_light',
      label: 'Low light',
      description: 'Simulates dimmer scenes with darker exposure, extra noise, and softer detail.'
    },
    {
      name: 'sensor_noise',
      label: 'Sensor noise',
      description: 'Adds rougher digital texture and a harsher capture feel for robustness testing.'
    },
    {
      name: 'warm_shift',
      label: 'Warm shift',
      description: 'Introduces warmer, sunlit color balance with a gentle exposure lift.'
    }
  ];

  let form = { ...initialForm };
  let options = {
    presets: ['mild', 'medium', 'strong'],
    recipes: fallbackRecipes
  };
  let currentJob = null;
  let runs = [];
  let isSubmitting = false;
  let loadError = '';
  let pollingHandle = null;
  let showAdvanced = false;

  onMount(() => {
    loadOptions();
    refreshRuns();

    return () => {
      if (pollingHandle) {
        clearInterval(pollingHandle);
      }
    };
  });

  async function loadOptions() {
    try {
      const response = await fetch('/api/options');
      if (!response.ok) throw new Error('Could not load options.');
      const data = await response.json();
      options = {
        presets: data.presets,
        recipes: data.recipes?.length ? data.recipes : fallbackRecipes
      };
      form = {
        ...form,
        ...data.defaults,
        recipes: data.defaults.recipes?.length ? [data.defaults.recipes[0]] : ['balanced'],
        overwrite_output: true
      };
    } catch (error) {
      loadError = error.message;
    }
  }

  async function refreshRuns() {
    try {
      const response = await fetch('/api/runs');
      if (!response.ok) throw new Error('Could not load runs.');
      runs = await response.json();
    } catch (error) {
      loadError = error.message;
    }
  }

  async function fetchJob(jobId) {
    const response = await fetch(`/api/runs/${jobId}`);
    if (!response.ok) throw new Error('Could not load run status.');
    currentJob = await response.json();
    await refreshRuns();

    if (currentJob.status === 'completed' || currentJob.status === 'failed') {
      stopPolling();
    }
  }

  function startPolling(jobId) {
    stopPolling();
    pollingHandle = setInterval(() => {
      fetchJob(jobId).catch((error) => {
        loadError = error.message;
        stopPolling();
      });
    }, 1500);
  }

  function stopPolling() {
    if (pollingHandle) {
      clearInterval(pollingHandle);
      pollingHandle = null;
    }
  }

  async function submitRun() {
    isSubmitting = true;
    loadError = '';

    try {
      const payload = normalizePayload(form);
      const response = await fetch('/api/runs', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });
      if (!response.ok) {
        const errorBody = await response.json().catch(() => ({}));
        throw new Error(errorBody.detail || 'Could not start run.');
      }
      currentJob = await response.json();
      startPolling(currentJob.job_id);
      await refreshRuns();
    } catch (error) {
      loadError = error.message;
    } finally {
      isSubmitting = false;
    }
  }

  async function selectRun(job) {
    currentJob = job;
    try {
      await fetchJob(job.job_id);
    } catch (error) {
      loadError = error.message;
    }

    if (job.status === 'running' || job.status === 'queued') {
      startPolling(job.job_id);
    }
  }

  function normalizePayload(values) {
    return {
      source: values.source.trim(),
      output_dataset_name: blankToNull(values.output_dataset_name),
      preset: values.preset,
      recipes: values.recipes.slice(0, 1),
      variant_count: Number(values.variant_count),
      seed: Number(values.seed),
      video_codec: 'avc1',
      max_videos: values.max_videos === '' ? null : Number(values.max_videos),
      skip_upload: values.skip_upload,
      private: false,
      overwrite_output: true,
      episode_index: 0
    };
  }

  function blankToNull(value) {
    return value && value.trim() ? value.trim() : null;
  }

  function formatStatus(status) {
    return status ? status.charAt(0).toUpperCase() + status.slice(1) : 'Unknown';
  }

  function formatTime(value) {
    if (!value) return 'Not started';
    return new Date(value).toLocaleString();
  }

  function jobVariants(job) {
    const variants = job?.result?.variants;
    if (Array.isArray(variants) && variants.length) return variants;

    if (job?.result && (job.result.visualizer_url || job.result.output_dir || job.result.resolved_repo_id)) {
      return [
        {
          label: job.config?.output_dataset_name || job.config?.output_repo_id || 'Dataset variant',
          seed: job.config?.seed,
          processed_videos: job.result.processed_videos,
          processed_frames: job.result.processed_frames,
          visualizer_url: job.result.visualizer_url,
          resolved_repo_id: job.result.resolved_repo_id,
          output_dir: job.result.output_dir
        }
      ];
    }

    return [];
  }

  function totalBatches(job) {
    if (!job) return 0;
    if (typeof job.total_variants === 'number' && job.total_variants > 0) return job.total_variants;

    const recipeCount = Array.isArray(job.config?.recipes) && job.config.recipes.length ? job.config.recipes.length : 1;
    const variantCount = Number(job.config?.variant_count) > 0 ? Number(job.config.variant_count) : 1;

    if (job.result || job.status === 'completed' || job.status === 'failed' || job.status === 'running') {
      return recipeCount * variantCount;
    }

    return 0;
  }

  function completedBatches(job) {
    if (!job) return 0;
    if (typeof job.completed_variants === 'number' && job.completed_variants > 0) return job.completed_variants;

    const total = totalBatches(job);
    if (job.status === 'completed' && total > 0) return total;

    return 0;
  }

  function recipeCount(job) {
    if (Array.isArray(job?.config?.recipes) && job.config.recipes.length) return job.config.recipes.length;
    return job?.result ? 1 : 0;
  }

  function progressPercent(job) {
    if (!job || !job.total_videos) return 6;
    return Math.max(6, Math.round((job.processed_videos / job.total_videos) * 100));
  }

  function batchProgressPercent(job) {
    const total = totalBatches(job);
    if (!total) return progressPercent(job);
    return Math.max(6, Math.round((completedBatches(job) / total) * 100));
  }

  function statusClasses(status) {
    if (status === 'completed') return 'bg-emerald-100 text-emerald-800';
    if (status === 'failed') return 'bg-rose-100 text-rose-700';
    if (status === 'running') return 'bg-amber-100 text-amber-700';
    return 'bg-slate-200 text-slate-700';
  }

  function toggleRecipe(recipeName) {
    form = { ...form, recipes: [recipeName] };
  }

  function isRecipeSelected(recipeName) {
    return form.recipes.includes(recipeName);
  }

  function selectedRecipeLabels() {
    return options.recipes.filter((recipe) => form.recipes.includes(recipe.name)).map((recipe) => recipe.label);
  }
</script>

<svelte:head>
  <title>Qualia Dataset Studio</title>
</svelte:head>

<main class="min-h-screen px-4 py-6 text-ink sm:px-6 lg:px-10">
  <div class="mx-auto flex max-w-7xl flex-col gap-6">
    <section class="relative overflow-hidden rounded-[2rem] border border-white/60 bg-ink px-6 py-8 text-white shadow-panel lg:px-8">
      <div class="absolute inset-y-0 right-0 hidden w-1/3 bg-[radial-gradient(circle_at_top,rgba(244,162,97,0.45),transparent_60%)] lg:block"></div>
      <div class="relative grid gap-6 lg:grid-cols-[1.2fr,0.8fr]">
        <div class="space-y-4">
          <p class="inline-flex rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs uppercase tracking-[0.24em] text-white/80">
            Qualia Dataset Studio
          </p>
          <div class="space-y-3">
            <h1 class="max-w-2xl font-display text-4xl font-semibold leading-tight sm:text-5xl">
              Augment your LeRobot dataset
            </h1>
            <p class="max-w-2xl text-sm text-slate-200 sm:text-base">
              Create a new dataset variant, track processing live, and open it in the Hugging Face visualizer when it is ready.
            </p>
          </div>
        </div>

        <div class="grid gap-3 rounded-[1.5rem] border border-white/15 bg-white/10 p-4 text-sm text-slate-100">
          <div class="flex items-center justify-between">
            <span>Processing engine</span>
            <span class="rounded-full bg-white/15 px-2 py-1 text-xs">Python</span>
          </div>
          <div class="flex items-center justify-between">
            <span>Run tracking</span>
            <span class="rounded-full bg-white/15 px-2 py-1 text-xs">Live jobs</span>
          </div>
          <div class="flex items-center justify-between">
            <span>Interface</span>
            <span class="rounded-full bg-white/15 px-2 py-1 text-xs">Svelte</span>
          </div>
          <div class="rounded-2xl bg-white/10 p-3 text-xs leading-6 text-slate-200">
            Built for local use on the same machine as the dataset tooling. The browser manages the workflow while the backend handles the heavy video processing and publishing.
          </div>
        </div>
      </div>
    </section>

    {#if loadError}
      <div class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
        {loadError}
      </div>
    {/if}

    <section class="grid gap-6 lg:grid-cols-[1.05fr,0.95fr]">
      <article class="glass relative z-20 rounded-[1.75rem] border border-white/70 p-5 shadow-panel sm:p-6">
        <div class="mb-5 flex items-center justify-between">
          <div>
            <p class="text-xs uppercase tracking-[0.24em] text-slate-500">New Run</p>
            <h2 class="mt-2 font-display text-2xl font-semibold text-ink">Configure a dataset variation</h2>
            <p class="mt-2 max-w-2xl text-sm text-slate-600">
              Start with the essential controls, keep browser-safe output by default, and only open advanced settings when you need finer control.
            </p>
          </div>
          <button
            class="rounded-full w-1/5 ml-2 bg-ink px-6 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
            on:click={submitRun}
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Starting run...' : 'Create run'}
          </button>
        </div>

        <div class="grid gap-4 sm:grid-cols-2">
          <label class="space-y-2 sm:col-span-2">
            <span class="flex items-center gap-2 text-sm font-medium text-slate-700">
              <span>Source dataset</span>
              <Tooltip text="The Hugging Face dataset id or local LeRobot dataset path to read from. In the common case this is a source like lerobot/aloha_static_cups_open." />
            </span>
            <input bind:value={form.source} class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none ring-0 transition focus:border-spruce" />
          </label>

          <label class="space-y-2">
            <span class="flex items-center gap-2 text-sm font-medium text-slate-700">
              <span>Output dataset name</span>
              <Tooltip text="The name for the generated dataset variant on Hugging Face. The studio combines this with your signed-in Hugging Face account automatically." />
            </span>
            <input bind:value={form.output_dataset_name} class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm focus:border-spruce" />
          </label>

          <label class="space-y-2">
            <span class="flex items-center gap-2 text-sm font-medium text-slate-700">
              <span>Intensity</span>
              <Tooltip text="Controls how strongly each selected augmentation recipe is applied. Use Strong when you want the change to be clearly visible, and lighter settings for subtler variation." />
            </span>
            <select bind:value={form.preset} class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm focus:border-spruce">
              {#each options.presets as preset}
                <option value={preset}>{preset}</option>
              {/each}
            </select>
          </label>

          <label class="space-y-2">
            <span class="flex items-center gap-2 text-sm font-medium text-slate-700">
              <span>Variants per recipe</span>
              <Tooltip text="Creates multiple dataset variants for each selected recipe. For example, 3 recipes and 2 variants per recipe will create 6 outputs with different seeds." />
            </span>
            <input bind:value={form.variant_count} type="number" min="1" class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm focus:border-spruce" />
          </label>

          <div class="space-y-3 sm:col-span-2">
            <div class="flex items-center gap-2 text-sm font-medium text-slate-700">
              <span>Augmentation tools</span>
              <Tooltip text="Choose one augmentation tool for this run. If you want to compare different looks, create a separate run for each tool." />
            </div>
            <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {#each options.recipes as recipe}
                <button
                  type="button"
                  class={`rounded-[1.4rem] border p-4 text-left transition ${
                    isRecipeSelected(recipe.name)
                      ? 'border-ink bg-ink text-white shadow-panel'
                      : 'border-slate-200 bg-white text-slate-700 hover:border-spruce/50'
                  }`}
                  on:click={() => toggleRecipe(recipe.name)}
                >
                  <div class="flex items-center justify-between gap-3">
                    <p class="font-semibold">{recipe.label}</p>
                    <span class={`rounded-full px-2 py-1 text-[11px] font-semibold ${
                      isRecipeSelected(recipe.name)
                        ? 'bg-white/15 text-white'
                        : 'bg-slate-100 text-slate-600'
                    }`}>
                      {isRecipeSelected(recipe.name) ? 'Selected' : 'Available'}
                    </span>
                  </div>
                  <p class={`mt-2 text-xs leading-5 ${isRecipeSelected(recipe.name) ? 'text-white/80' : 'text-slate-500'}`}>
                    {recipe.description}
                  </p>
                </button>
              {/each}
            </div>
            <p class="text-xs text-slate-500">
              Selected tool: {selectedRecipeLabels()[0] ?? 'None'}
            </p>
          </div>

          <div class="sm:col-span-2 rounded-[1.5rem] border border-slate-200 bg-white p-4">
            <button
              type="button"
              class="flex w-full items-center justify-between text-left"
              on:click={() => showAdvanced = !showAdvanced}
            >
              <div>
                <p class="text-sm font-semibold text-ink">Advanced controls</p>
                <p class="mt-1 text-xs text-slate-500">Use these when you are smoke-testing, reproducing a run, or keeping the output local.</p>
              </div>
              <span class="rounded-full border border-slate-300 px-3 py-1 text-xs font-medium text-slate-600">
                {showAdvanced ? 'Hide' : 'Show'}
              </span>
            </button>

            {#if showAdvanced}
              <div class="mt-4 grid gap-4 sm:grid-cols-2">
                <label class="space-y-2">
                  <span class="flex items-center gap-2 text-sm font-medium text-slate-700">
                    <span>Seed</span>
                    <Tooltip text="Controls deterministic randomness for the sampled transformations. Reusing the same seed lets you reproduce a run exactly, which is useful for comparisons and debugging." />
                  </span>
                  <input bind:value={form.seed} type="number" class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm focus:border-spruce" />
                </label>

                <label class="space-y-2">
                  <span class="flex items-center gap-2 text-sm font-medium text-slate-700">
                    <span>Videos to process</span>
                    <Tooltip text="Limits how many source videos are augmented inside each generated dataset variant. Leave this at a low number for fast smoke tests, then raise it when you are ready to process the full dataset." />
                  </span>
                  <input bind:value={form.max_videos} type="number" min="1" class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm focus:border-spruce" />
                </label>

                <div class="space-y-2">
                  <span class="flex items-center gap-2 text-sm font-medium text-slate-700">
                    <span>Skip Hugging Face upload</span>
                    <Tooltip text="Runs the full pipeline locally but stops before publishing. This is useful when you want to check the generated files first or run a quick local smoke test." />
                  </span>
                  <label class="flex h-[50px] items-center justify-between rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700">
                    <span>{form.skip_upload ? 'Upload disabled for this run' : 'Upload enabled for this run'}</span>
                    <input bind:checked={form.skip_upload} type="checkbox" class="h-4 w-4 rounded border-slate-300 text-spruce focus:ring-spruce" />
                  </label>
                </div>

                <div class="sm:col-span-2 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-xs leading-6 text-amber-900">
                  The UI always uses browser-safe <span class="font-semibold">avc1 / H.264</span> output. The older local-only codec option is intentionally hidden here to avoid generating videos that fail to play in the browser visualizer.
                </div>
              </div>
            {/if}
          </div>
        </div>
      </article>

      <article class="glass relative z-10 rounded-[1.75rem] border border-white/70 p-5 shadow-panel sm:p-6">
        <div class="mb-5 flex items-start justify-between gap-4">
          <div>
            <p class="text-xs uppercase tracking-[0.24em] text-slate-500">Run Activity</p>
            <h2 class="mt-2 font-display text-2xl font-semibold text-ink">Track progress as the dataset is prepared</h2>
          </div>
          {#if currentJob}
            <span class={`rounded-full px-3 py-1 text-xs font-semibold ${statusClasses(currentJob.status)}`}>
              {formatStatus(currentJob.status)}
            </span>
          {/if}
        </div>

        {#if currentJob}
          <div class="space-y-5">
            <div class="rounded-[1.5rem] border border-slate-200 bg-white p-4">
              <div class="flex items-center justify-between text-sm text-slate-600">
                <span>{currentJob.phase}</span>
                <span>{completedBatches(currentJob)}/{totalBatches(currentJob) || '?' } batches</span>
              </div>
              <div class="mt-3 h-3 overflow-hidden rounded-full bg-slate-200">
                <div class="h-full rounded-full bg-gradient-to-r from-glow via-coral to-spruce transition-all duration-300" style={`width: ${batchProgressPercent(currentJob)}%`}></div>
              </div>
              <p class="mt-3 text-sm text-slate-700">{currentJob.message}</p>
              {#if currentJob.current_variant}
                <p class="mt-2 text-xs text-slate-500">Current batch: {currentJob.current_variant}</p>
              {/if}
              {#if currentJob.current_video}
                <p class="mt-2 text-xs text-slate-500">Current video: {currentJob.current_video}</p>
              {/if}
              {#if currentJob.status === 'completed' && jobVariants(currentJob).some((variant) => variant.visualizer_url)}
                <div class="mt-4 flex flex-wrap gap-2">
                  {#each jobVariants(currentJob).filter((variant) => variant.visualizer_url) as variant}
                    <a
                      href={variant.visualizer_url}
                      target="_blank"
                      rel="noreferrer"
                      class="inline-flex rounded-full bg-ink px-4 py-2 text-xs font-semibold text-white transition hover:bg-slate-800"
                    >
                      View {variant.label}
                    </a>
                  {/each}
                </div>
              {/if}
            </div>

            <div class="grid gap-3 sm:grid-cols-3">
              <div class="rounded-[1.5rem] bg-slate-50 p-4">
                <p class="text-xs uppercase tracking-[0.18em] text-slate-500">Batches</p>
                <p class="mt-2 text-sm text-slate-700">{completedBatches(currentJob)}/{totalBatches(currentJob)}</p>
              </div>
              <div class="rounded-[1.5rem] bg-slate-50 p-4">
                <p class="text-xs uppercase tracking-[0.18em] text-slate-500">Started</p>
                <p class="mt-2 text-sm text-slate-700">{formatTime(currentJob.started_at)}</p>
              </div>
              <div class="rounded-[1.5rem] bg-slate-50 p-4">
                <p class="text-xs uppercase tracking-[0.18em] text-slate-500">Finished</p>
                <p class="mt-2 text-sm text-slate-700">{formatTime(currentJob.finished_at)}</p>
              </div>
            </div>

            {#if currentJob.result}
              <div class="rounded-[1.5rem] border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
                <p class="font-semibold">Run results</p>
                <p class="mt-2 text-emerald-800">
                  Generated {jobVariants(currentJob).length} variant(s) from {recipeCount(currentJob)} selected recipe(s).
                </p>
                <div class="mt-4 grid gap-3">
                  {#each jobVariants(currentJob) as variant}
                    <div class="rounded-[1.25rem] border border-emerald-200 bg-white/80 p-4">
                      <div class="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p class="font-semibold text-emerald-950">{variant.label}</p>
                          <p class="mt-1 text-xs text-emerald-800">Seed {variant.seed} · {variant.processed_videos} video(s) · {variant.processed_frames} frames</p>
                        </div>
                        {#if variant.visualizer_url}
                          <a href={variant.visualizer_url} target="_blank" rel="noreferrer" class="inline-flex rounded-full bg-emerald-700 px-4 py-2 font-medium text-white transition hover:bg-emerald-800">
                            View in visualizer
                          </a>
                        {/if}
                      </div>
                      {#if variant.resolved_repo_id}
                        <p class="mt-3 break-all text-xs text-emerald-900"><span class="font-medium">Published as:</span> {variant.resolved_repo_id}</p>
                      {/if}
                      {#if variant.output_dir}
                        <p class="mt-2 break-all text-xs text-emerald-900"><span class="font-medium">Saved to:</span> {variant.output_dir}</p>
                      {/if}
                    </div>
                  {/each}
                </div>
              </div>
            {/if}

            <div class="rounded-[1.5rem] border border-slate-200 bg-slate-950 p-4 text-xs text-slate-100">
              <div class="mb-3 flex items-center justify-between">
                <p class="uppercase tracking-[0.18em] text-slate-400">Activity log</p>
                <button class="text-slate-300 transition hover:text-white" on:click={() => currentJob && fetchJob(currentJob.job_id)}>
                  Refresh
                </button>
              </div>
              <div class="max-h-[20rem] space-y-2 overflow-auto pr-2">
                {#each currentJob.logs as entry}
                  <p class="rounded-xl bg-white/5 px-3 py-2 leading-5">{entry}</p>
                {/each}
              </div>
            </div>
          </div>
        {:else}
          <div class="rounded-[1.5rem] border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-sm text-slate-500">
            Start a run to see progress, output details, and publishing activity here.
          </div>
        {/if}
      </article>
    </section>

    <section class="grid gap-6 lg:grid-cols-[0.8fr,1.2fr]">
      <article class="glass rounded-[1.75rem] border border-white/70 p-5 shadow-panel sm:p-6">
        <p class="text-xs uppercase tracking-[0.24em] text-slate-500">Getting Started</p>
        <h2 class="mt-2 font-display text-2xl font-semibold text-ink">Launch the studio and test batch generation</h2>
        <div class="mt-4 space-y-4 text-sm leading-6 text-slate-700">
          <div class="rounded-[1.35rem] border border-slate-200 bg-white p-4">
            <p class="text-xs uppercase tracking-[0.18em] text-slate-500">1. Start the processing service</p>
            <p class="mt-2 font-medium text-ink">The backend handles dataset downloads, video augmentation, and publishing.</p>
            <pre class="mt-3 overflow-x-auto rounded-2xl bg-slate-950 px-4 py-3 text-xs text-slate-100"><code>.\.venv2\Scripts\Activate.ps1
qualia-augment-web</code></pre>
          </div>

          <div class="rounded-[1.35rem] border border-slate-200 bg-white p-4">
            <p class="text-xs uppercase tracking-[0.18em] text-slate-500">2. Start the UI in dev mode if needed</p>
            <p class="mt-2 font-medium text-ink">You only need the Vite dev server when making UI changes. Otherwise the built app served by the backend is enough.</p>
            <pre class="mt-3 overflow-x-auto rounded-2xl bg-slate-950 px-4 py-3 text-xs text-slate-100"><code>cd frontend
npm run dev</code></pre>
          </div>

          <div class="rounded-[1.35rem] border border-slate-200 bg-slate-50 p-4">
            <p class="text-xs uppercase tracking-[0.18em] text-slate-500">3. Open the studio</p>
            <p class="mt-2">Use <span class="font-semibold">http://127.0.0.1:8000</span> for the built app served by the backend, or <span class="font-semibold">http://127.0.0.1:5173</span> if you started the frontend dev server.</p>
          </div>

          <div class="rounded-[1.35rem] border border-amber-200 bg-amber-50 p-4 text-amber-900">
            <p class="font-medium">Recommended first run</p>
            <p class="mt-2">Choose <span class="font-semibold">Strong</span>, keep <span class="font-semibold">1 video</span>, and pick a single tool to confirm the pipeline and visualizer are working before you scale up.</p>
          </div>
        </div>
      </article>

      <article class="glass rounded-[1.75rem] border border-white/70 p-5 shadow-panel sm:p-6">
        <div class="mb-4 flex items-center justify-between">
          <div>
            <p class="text-xs uppercase tracking-[0.24em] text-slate-500">Run History</p>
            <h2 class="mt-2 font-display text-2xl font-semibold text-ink">Reopen previous runs</h2>
          </div>
          <button class="rounded-full border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50" on:click={refreshRuns}>
            Refresh
          </button>
        </div>

        <div class="grid gap-3">
          {#if runs.length}
            {#each runs as run}
              <button class="rounded-[1.5rem] border border-slate-200 bg-white p-4 text-left transition hover:-translate-y-0.5 hover:border-spruce/50 hover:shadow-panel" on:click={() => selectRun(run)}>
                <div class="flex items-start justify-between gap-4">
                  <div>
                    <p class="text-sm font-semibold text-ink">{run.config.output_dataset_name || run.config.output_repo_id || 'Local-only run'}</p>
                    <p class="mt-1 text-xs text-slate-500">{run.config.source}</p>
                    <p class="mt-1 text-xs text-slate-500">
                      {run.config.recipes?.length ?? 1} recipe(s) · {run.config.variant_count ?? 1} variant(s) each
                    </p>
                  </div>
                  <span class={`rounded-full px-3 py-1 text-[11px] font-semibold ${statusClasses(run.status)}`}>
                    {formatStatus(run.status)}
                  </span>
                </div>
                <p class="mt-3 text-sm text-slate-600">{run.message}</p>
                <p class="mt-2 text-xs text-slate-500">{formatTime(run.created_at)}</p>
                {#if run.result?.variants?.some((variant) => variant.visualizer_url)}
                  <div class="mt-3 flex flex-wrap gap-2">
                    {#each run.result.variants.filter((variant) => variant.visualizer_url) as variant}
                      <a
                        href={variant.visualizer_url}
                        target="_blank"
                        rel="noreferrer"
                        class="inline-flex rounded-full border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 transition hover:border-spruce hover:text-spruce"
                        on:click|stopPropagation
                      >
                        View {variant.label}
                      </a>
                    {/each}
                  </div>
                {/if}
              </button>
            {/each}
          {:else}
            <div class="rounded-[1.5rem] border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-sm text-slate-500">
              No runs yet. Create your first dataset variation to build a history here.
            </div>
          {/if}
        </div>
      </article>
    </section>
  </div>
</main>
