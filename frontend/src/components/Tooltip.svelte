<script>
  export let text = '';
</script>

<span class="group relative z-[90] inline-flex">
  <button
    type="button"
    class="inline-flex h-5 w-5 items-center justify-center rounded-full border border-slate-300 bg-white text-[11px] font-bold text-slate-500 transition hover:border-spruce hover:text-spruce focus:border-spruce focus:text-spruce focus:outline-none"
    aria-label={text}
  >
    i
  </button>
  <span class="pointer-events-none invisible absolute left-0 top-full z-[100] mt-2 w-72 rounded-2xl bg-ink px-3 py-2 text-left text-xs font-normal leading-5 text-white opacity-0 shadow-2xl transition group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100">
    {text}
  </span>
</span>
