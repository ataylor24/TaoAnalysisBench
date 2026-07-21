# TaoBenchAnalysis — full release (v1.0.0)

A self-contained release: the 600-exercise paired Lean 4 dataset, both
versions of the Tao Analysis textbook source (annotated with our
LLM-curated `Tags/` companion modules and the original without them),
the agentic data-construction pipelines that produced the dataset, the
Lean REPL harness, the inference verification scripts, and the
visualization tooling.

## What's here

```
TaoBenchAnalysis_code/
├── README.md
├── croissant.json                   # MLCommons Croissant 1.0 metadata
├── LICENSE                          # MIT
├── requirements.txt                 # Python deps (openai-agents + python-dotenv)
├── .env.template                    # copy to .env and fill in OPENAI_API_KEY
│
├── data/                            # ── DATA ──
│   ├── TaoBenchAnalysis_textbook.jsonl  # 600 textbook-flavored exercises
│   ├── TaoBenchAnalysis_mathlib.jsonl   # 600 Mathlib-only restatements
│   ├── textbook_annotated/          # Tao Analysis source + 74 LLM-curated Tags/ modules
│   │   ├── Analysis.lean
│   │   ├── lakefile.toml
│   │   ├── lean-toolchain
│   │   └── Analysis/
│   │       ├── Section_*.lean       (74 sections)
│   │       ├── Appendix_*.lean      (9 appendices)
│   │       ├── Tags/                (74 LLM-curated tag modules) ← ANNOTATIONS
│   │       └── MeasureTheory/, Misc/, Tools/
│   └── textbook_original/           # the same source MINUS Analysis/Tags/
│
├── agent/                           # ── AGENTIC PIPELINES ──
│   ├── globals.py                   # path/runtime config (env-var driven)
│   ├── system_prompts.py            # shared agent system-prompt fragments
│   ├── tagging_workflow.py          # LLM-curated simp/aesop/grind tags
│   ├── relaxation_workflow.py       # progenitor-relaxed dataset construction
│   ├── mathlib_translation_workflow.py   # Tao→Mathlib restatement
│   ├── add_tags_imports.py          # post-hoc Tags-import injection
│   └── toolchest/                   # agent tools
│       ├── extract_goal_state.py    # Jixia-backed goal-state probe
│       ├── file_look_up.py          # textbook source lookup
│       └── repl_pool/               # vendored REPL worker pool
│           ├── compile_lean_code.py
│           └── simple_worker.py
│
├── verification/                    # ── INFERENCE VERIFICATION ──
│   ├── verify_inference.py          # main verifier (compiles via REPL pool)
│   └── recompile_relaxed_tagged.py  # post-hoc Tags-import recompile
│
├── visualization/
│   └── build_tagging_viewer.py      # produces tagging_viewer.html
│
└── lean_runtime/                    # ── LEAN REPL HOST ──
    ├── lakefile.toml                # mathlib v4.26.0 + repl v4.26.0 deps
    ├── lean-toolchain               # leanprover/lean4:v4.26.0
    └── ReplV4_26_0.lean             # tiny stub library
```

## The two textbook versions

- **`data/textbook_annotated/`** — Tao's textbook formalization PLUS
  74 LLM-curated companion modules under `Analysis/Tags/` that attach
  `simp` / `aesop safe` / `aesop unsafe N%` / `grind <modifier>`
  attributes to **1521 of 1865** named declarations. Importing
  `Analysis.Tags.Section_X_Y` makes textbook lemmas reachable by
  search-style tactics the way Mathlib's tagged lemmas are.
- **`data/textbook_original/`** — the same source tree with `Tags/`
  removed. Useful as a clean baseline / for reproducing the annotated
  version from scratch.

The two trees are otherwise identical.

## What's not here

- **Mathlib v4.26.0 oleans.** Pulled by `lake update + cache get` in
  `lean_runtime/` and `data/textbook_annotated/` on first run. ~6 GB.
- **Jixia.** Only needed for the mathlib translation workflow's
  goal-state tool. Apache-2.0; install separately from
  <https://github.com/marcusrossel/jixia> and set `JIXIA_EXECUTABLE`.

## Setup

```bash
# 1. Python deps
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Copy env template
cp .env.template .env
# edit .env to set OPENAI_API_KEY

# 3. Build the Lean runtime (one-time)
cd lean_runtime
lake update
lake exe cache get      # ~6 GB pre-built mathlib oleans
lake build repl
cd ..

# 4. Unpack the data release somewhere and point at it
export ANALYSIS_BOOK_DIRECTORY=/path/to/TaoBenchAnalysis_release/textbook_source/Analysis
```

## The three agentic pipelines

### `agent/tagging_workflow.py` — textbook lemma tag attribution
Per-section: parses every named theorem/lemma/instance, asks an agent
(gpt-5.5, high reasoning) to attach `simp` / `aesop safe` /
`aesop unsafe N%` / `grind <modifier>` per a tag-criteria prompt. Then a
**critique-pass** second agent reviews the first pass's output. After
each pass a **build-validate-strip** routine runs `lake build` on the
generated `Tags/<Section>.lean` module and removes any tag Lean rejects
(e.g., bare `[grind]` on non-equational facts). Resume-safe: runs are
streamed to `output/textbook_tags/results_stream.jsonl`.

```bash
cd agent
TAG_CONCURRENT=20 python tagging_workflow.py
# subset: TAG_ONLY=Section_5_5,Section_7_1 python tagging_workflow.py
```

### `agent/relaxation_workflow.py` — relaxed dataset construction
Per FQN: reads the progenitor section, strips proven theorems
(`R5b/R6` rules), forces target body to `:= by sorry`, prepends `import
Mathlib + import Analysis.<dep>` per dep, and verifies via the REPL
pool. Includes a fallback note for chapters where `import Mathlib` causes
destructive typeclass collisions (Chapter 2/3 etc.) and a per-FQN hint
table for known input-data quirks.

```bash
cd agent
RELAX_CONCURRENT=20 RELAX_MAX_TURNS=35 python relaxation_workflow.py
```

### `agent/mathlib_translation_workflow.py` — Tao → Mathlib
Per exercise: an agent translates from Tao's reconstructed types to
standard Mathlib v4.26.0 idioms. Has tools to compile via the REPL pool
and to extract goal states (via Jixia) for diffing the original vs the
translation. An independent compile gate doesn't trust the agent's
self-judgment — re-compiles the extracted output before marking
success.

```bash
cd agent
TRANSLATE_MAX_TURNS=30 python mathlib_translation_workflow.py
```

## The REPL harness (`agent/toolchest/repl_pool/`)

A persistent pool of `lake exe repl` worker processes, one Mathlib
import preloaded per worker (~1.5 GB resident each). The pool exposes
`compile_lean_file_string(code: str) -> dict` for sending an entire
Lean file to a worker and getting `{success, error, first_error_line,
messages}` back. All three pipelines and `verify_inference.py` use this
as their compile gate.

## Verification (`verification/`)

`verify_inference.py` is the inference-result verifier shipped in the
verifier package. Reads a JSONL of model attempts, looks up each
canonical slice by FQN, splices the model's proof body into the slice,
and compiles via the REPL pool. Output is one JSONL row per attempt
with `success`, `error`, `first_error_line`.

`recompile_relaxed_tagged.py` is the harness used to validate that
post-hoc `Analysis.Tags.<Section>` imports don't break the relaxed
dataset's compilability — runs the same REPL pool against a JSONL of
Lean files in parallel.

## Visualization (`visualization/`)

`build_tagging_viewer.py` reads the generated `Tags/<Section>.lean`
modules + the `results_stream.jsonl` from a tagging run and produces a
self-contained HTML viewer with a per-section sidebar, inline
syntax-highlighted Lean source, and tag-distribution stats.

## License

This code is released under the MIT License. The bundled Lean runtime
(`lean_runtime/`) is a minimal Lake project that pulls Mathlib (Apache
2.0) and the official Lean REPL (Apache 2.0) at v4.26.0.

## Citation

```
@misc{taobench_analysis_code_2026,
  title  = {TaoBenchAnalysis: Code release for the agentic data
            construction and verification pipelines},
  year   = {2026},
  howpublished = {Code release v1.0.0}
}
```
