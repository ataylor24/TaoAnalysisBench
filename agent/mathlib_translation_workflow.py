"""
Agentic Mathlib Translation Workflow

Translates Tao Analysis exercises (using local definitions) into equivalent
Mathlib-only formulations. Each exercise is handled by a single agent that
iterates up to MAX_TURNS, using tools to compile, extract goal states,
and optionally search the web.

Usage:
    cd src/agent
    python mathlib_translation_workflow.py
"""

import dotenv
dotenv.load_dotenv()
# import weave  # optional tracing; pip install weave + uncomment
from agents import Agent, Runner, SQLiteSession, ModelSettings
from openai.types.shared import Reasoning
from agents.exceptions import MaxTurnsExceeded
import asyncio
import os
import json
import re
from pathlib import Path

from toolchest.repl_pool import (
    compile_lean_file,
    compile_lean_file_string,
    initialize_repl_manager,
    shutdown_repl_manager,
)
from toolchest.extract_goal_state import extract_goal_state
from agents import function_tool
from globals import OUTPUT_DIR
# weave.init("...")  # optional tracing
# ── Configuration ──────────────────────────────────────────────────────
MAX_CONCURRENT = 20
MAX_TURNS = int(os.environ.get("TRANSLATE_MAX_TURNS", "30"))
MODEL = "gpt-5.1"
DATASET_PATH = os.environ.get(
    "TRANSLATE_DATASET",
    "/Users/researcher/Desktop/lean_prover/src/agent/output/results_clean.jsonl",
)
RESULTS_DIR = os.path.join(OUTPUT_DIR, "mathlib_translation")
os.makedirs(RESULTS_DIR, exist_ok=True)

# Standardized Lean toolchain (textbook is also pinned to this commit)
REPL_WORKSPACE = os.environ.get("LEAN_RUNTIME", "")
LEAN_VERSION = "leanprover/lean4:v4.26.0"
# REPL workers in the pool. Memory-bound: each ~1-2 GB on a 16 GB box.
REPL_WORKERS = int(os.environ.get("REPL_WORKERS", "4"))


# ── Tools ──────────────────────────────────────────────────────────────

@function_tool
def compile_mathlib_code(code: str) -> str:
    """Compile a Lean4 file (imports + defs + theorems) against a Mathlib
    v4.26.0 environment via the persistent REPL pool. Returns either a success
    message or a JSON-wrapped error report between LEAN_COMPILE_RESULT markers.
    """
    return compile_lean_file_string(code)


@function_tool
def get_goal_state(lean_code: str) -> str:
    """Extract the final proof goal state from a Lean4 snippet using Jixia.
    The snippet should end with `by sorry` so the goal state reflects the
    full proof obligation. Returns the goal state as a string with
    hypotheses and the ⊢ goal."""
    return extract_goal_state(lean_code)


# ── System Prompt ──────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert Lean4 and Mathlib translator. Your job is to translate
exercises from Terence Tao's Analysis I textbook — which use local definitions and custom
notation — into equivalent formulations that use ONLY standard Mathlib definitions.

## Workflow

On each turn you should:

1. **Translate** (or revise) the exercise into a Mathlib-only version.
2. **Compile** it using the `compile_mathlib_code` tool.
3. If compilation fails, read the errors and fix them on the next attempt.
4. Once it compiles, use `get_goal_state` on BOTH the original Tao version
   AND your Mathlib version to extract their proof goal states.
5. Compare the two goal states. If they express the same mathematical statement
   (allowing for standard equivalences, variable renaming, and notation differences),
   you are done. If not, revise your translation.

## Output Format

When you have a version that both compiles and is mathematically equivalent,
return your final answer with this exact format:

### Mathlib Version:
```lean4
import Mathlib
import Aesop
set_option maxHeartbeats 0
open BigOperators Real Nat Topology Rat Set Filter

namespace TaoBench

{your theorem declaration ending with := by sorry}

end TaoBench
```

### Equivalence Judgment:
{Yes or No — are the goal states mathematically equivalent?}

## Rules

- The declaration must keep the SAME NAME as the original.
- **The declaration body MUST be exactly `:= by sorry`** — even if the source
  ships a real proof and even if you could prove it yourself. We are producing a
  benchmark prompt; the body must be `sorry` so the model under test has work to
  do. Do NOT include any tactic block other than `sorry`.
- You may ONLY use: `import Mathlib`, `import Aesop`, and the `open` line above.
- Do NOT add any other imports.
- You may use `compile_mathlib_code` and `get_goal_state` as many times as needed.
- You may use web search to look up Mathlib API names if needed.
- **Preserve the source declaration KEYWORD.** If the original is `def`/`abbrev`/
  `instance`/`class`, your translation must use the same keyword — not `theorem`.
  In particular, Tao's `instance` declarations stay `instance`, not converted to
  `theorem`.

## ABSOLUTE: Exactly one top-level declaration

Your output MUST contain EXACTLY ONE top-level declaration: the target itself.
No extra `abbrev`/`def`/`structure`/`instance`/`class`/`inductive`/`theorem`/`lemma`.

If the original Tao theorem references a Tao-specific predicate or notion that
isn't in Mathlib (e.g. `Sequence.subseq`, `axiom_of_universal_specification`,
`Rat.Steady`, `BoundedInterval`, `Sequence.IsCauchy`), you MUST either:

(a) **Replace it with the Mathlib equivalent.** Search Mathlib first — many
    "axioms" Tao introduces are TRIVIALLY TRUE in Mathlib. For example:
    - `axiom_of_universal_specification α` — trivially true: `Set α := α → Prop`,
      witness is `setOf P`. Drop the hypothesis entirely.
    - `axiom_of_choice` — `Classical.choice` / `Classical.choose` is built-in.
    - `Sequence.IsCauchy` over Tao's quotient `Real` — use Mathlib's `CauchySeq`.
    - `BoundedInterval` — use `Set.Icc`/`Ico`/`Ioc`/`Ioo` (or just `Set.Ioc a b ∪ …`).

(b) **Inline the predicate's body** into the theorem statement directly.

### EXAMPLE — INCORRECT (introduces helper):
```lean4
abbrev Sequence.subseq (a b : ℕ → ℝ) : Prop :=
  ∃ f : ℕ → ℕ, StrictMono f ∧ ∀ n, b n = a (f n)
theorem Sequence.subseq_self (a : ℕ → ℝ) : Sequence.subseq a a := by sorry
```

### EXAMPLE — CORRECT (inlines the predicate):
```lean4
theorem Sequence.subseq_self (a : ℕ → ℝ) :
    ∃ f : ℕ → ℕ, StrictMono f ∧ ∀ n, a n = a (f n) := by sorry
```

### EXAMPLE — INCORRECT (carries Tao's axiom hypothesis):
```lean4
abbrev axiom_of_universal_specification (α : Type u) : Prop :=
  ∀ P : α → Prop, ∃ A : Set α, ∀ x, x ∈ A ↔ P x
theorem singleton_exists (h : axiom_of_universal_specification α) (x : α) :
    ∃ X : Set α, ∀ y, y ∈ X ↔ y = x := by sorry
```

### EXAMPLE — CORRECT (drops the redundant axiom; uses Mathlib's `Set` directly):
```lean4
theorem singleton_exists (x : α) :
    ∃ X : Set α, ∀ y, y ∈ X ↔ y = x := by sorry
```

If you cannot eliminate every helper this way, the translation is wrong — keep
trying. Even one extra top-level declaration disqualifies the output.

## Mapping Tao chapter abstractions to Mathlib

When you see these Tao notions, use the listed Mathlib counterparts directly —
do NOT inline encodings using primitive types:

- `Chapter11.BoundedInterval` (Tao's inductive `Ioo|Icc|Ioc|Ico` over `ℝ`):
    use `Set ℝ` with `Set.Icc a b` / `Set.Ico a b` / `Set.Ioc a b` / `Set.Ioo a b`.
    DO NOT encode an interval as `(ℝ × ℝ) × (Bool × Bool)` and inline a
    membership predicate `if cl then a ≤ x else a < x ∧ …`. That is bloat.
- `Chapter11.Partition` over `BoundedInterval`: use `Finset (Set ℝ)` with the
    corresponding Mathlib partition formulation, or unfold the partition
    structure inline using `Finset.sum` / `Set.disjoint_iff`.
- `Chapter11.PiecewiseConstantOn` / `IntegrableOn` / `α_length` / Riemann–
    Stieltjes machinery: use `MeasureTheory.IntervalIntegrable`, `StepFunction`,
    `MeasureTheory.integral`, and friends. If unsure, search Mathlib for
    `intervalIntegral`, `MeasureTheory.SimpleFunc`, `StieltjesFunction`.
- Tao's quotient `Real` (Cauchy sequences mod equiv): just use Mathlib's `ℝ`.
- Tao's quotient `Rat` (`PreRat` mod equiv): just use Mathlib's `ℚ`.
"""


# ── Query Construction ─────────────────────────────────────────────────

def normalize_sorry(text: str) -> str:
    """Ensure the last `:= by sorry` is properly formatted."""
    pattern = re.compile(r":= by\s+sorry\b")
    matches = list(pattern.finditer(text))
    if not matches:
        return text
    last = matches[-1]
    return text[:last.start()] + ":= by\n  sorry" + text[last.end():]


def build_translation_query(exercise: dict) -> str:
    """Build the initial prompt for the translation agent."""
    tao_code = (exercise.get("Tao_Version") or exercise.get("content", "")).strip()

    return f"""Please translate the following Tao Analysis exercise into a Mathlib-only version.

### Original Tao Exercise:
```lean4
{tao_code}
```

Chapter: {exercise.get('chapter_name', 'unknown')}
Exercise: {exercise.get('exercise_enumeration', exercise.get('FQN', 'unknown'))}

Begin by analyzing what this exercise means mathematically, then produce a Mathlib translation.
Use the tools to compile and verify your translation."""


# ── Agent Definition ───────────────────────────────────────────────────

Translation_Agent = Agent(
    name="Mathlib Translation Agent",
    model=MODEL,
    instructions=SYSTEM_PROMPT,
    tools=[compile_mathlib_code, get_goal_state],
    model_settings=ModelSettings(
        reasoning=Reasoning(effort="high")
    ),
)


# ── Per-Exercise Processing ────────────────────────────────────────────

async def process_exercise(idx: int, exercise: dict, sem: asyncio.Semaphore):
    async with sem:
        query = build_translation_query(exercise)
        session = SQLiteSession(f"mathlib_translation_{idx}")

        agent_finished = False
        run_error = None
        output_text = ""
        try:
            result = await Runner.run(
                Translation_Agent,
                input=query,
                session=session,
                max_turns=MAX_TURNS,
            )
            output_text = result.final_output
            agent_finished = True
        except MaxTurnsExceeded as e:
            output_text = str(e)
            run_error = {"type": "MaxTurnsExceeded", "message": str(e)}
        except Exception as e:
            output_text = str(e)
            run_error = {"type": type(e).__name__, "message": str(e)}

        # Extract the Mathlib version from the output (regardless of agent
        # finishing cleanly — sometimes max-turns hits after the agent
        # already emitted a final block).
        mathlib_code = None
        equivalence = None
        if output_text:
            code_match = re.search(
                r"### Mathlib Version:\s*```lean4\s*(.*?)```",
                output_text, re.DOTALL
            )
            if code_match:
                mathlib_code = code_match.group(1).strip()

            eq_match = re.search(
                r"### Equivalence Judgment:\s*(\w+)",
                output_text, re.MULTILINE
            )
            if eq_match:
                equivalence = eq_match.group(1).strip().lower()

        # Independent compile gate — `success` no longer trusts the agent's
        # self-judgment. We re-compile the extracted mathlib_code via the REPL
        # pool and only mark success if the pool reports success.
        compile_result = None
        success = False
        if mathlib_code:
            compile_result = await asyncio.to_thread(compile_lean_file, mathlib_code)
            success = bool(compile_result.get("success"))

        return {
            "index": idx,
            "chapter_name": exercise.get("chapter_name", ""),
            "FQN": exercise.get("theorem_name", exercise.get("FQN", "")),
            "exercise_enumeration": exercise.get("exercise_enumeration", ""),
            "lean_version": LEAN_VERSION,
            "agent_finished": agent_finished,
            "success": success,  # gated on REPL compile, not agent claim
            "equivalence": equivalence,  # agent's self-judgment, retained for record
            "mathlib_code": mathlib_code,
            "tao_code": (exercise.get("Tao_Version") or exercise.get("content", "")).strip(),
            "compile_result": compile_result,
            "run_error": run_error,
            "raw_output": output_text if not success else None,
        }


# ── Main ───────────────────────────────────────────────────────────────

async def main():
    # Load dataset
    with open(DATASET_PATH) as f:
        data = [json.loads(line) for line in f if line.strip()]

    # Skip already-completed exercises (success=True now means real compile).
    # FQNs in TRANSLATE_FORCE bypass the skip — used for re-translating entries
    # whose original Tao slice was broken.
    results_path = os.path.join(RESULTS_DIR, "results_stream.jsonl")
    force_env = os.environ.get("TRANSLATE_FORCE", "").strip()
    force_retry = set(f for f in force_env.split(",") if f) if force_env else set()
    if force_retry:
        print(f"TRANSLATE_FORCE: bypass resume for {len(force_retry)} FQNs")
    already_done = set()
    if os.path.exists(results_path):
        with open(results_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    if r.get("success") and r.get("FQN") not in force_retry:
                        already_done.add(r["FQN"])

    # Filter to exercises not yet done.
    # TRANSLATE_ONLY env var: comma-separated FQNs to run a subset (smoke test
    # / targeted retry). When unset, run everything that isn't already done.
    only_env = os.environ.get("TRANSLATE_ONLY", "").strip()
    TEST_FQNS = set(only_env.split(",")) if only_env else None

    exercises = []
    for i, entry in enumerate(data):
        fqn = entry.get("theorem_name", entry.get("FQN", ""))
        if fqn and fqn not in already_done:
            if TEST_FQNS is not None and fqn not in TEST_FQNS:
                continue
            entry["_idx"] = i
            exercises.append(entry)

    print(f"Total exercises: {len(data)}")
    print(f"Already done: {len(already_done)}")
    print(f"To process: {len(exercises)}")

    if not exercises:
        print("Nothing to do.")
        return

    # Boot the REPL pool. The agent's compile_mathlib_code tool and the final
    # compile gate both pull workers from this pool.
    print(f"Booting REPL pool: workspace={REPL_WORKSPACE} workers={REPL_WORKERS}")
    initialize_repl_manager(REPL_WORKSPACE, REPL_WORKERS, verbose=False)
    try:
        sem = asyncio.Semaphore(MAX_CONCURRENT)
        tasks = [
            process_exercise(ex["_idx"], ex, sem)
            for ex in exercises
        ]

        total = len(tasks)
        for i, coro in enumerate(asyncio.as_completed(tasks), start=1):
            res = await coro
            if res["success"]:
                tag = "OK" if res.get("equivalence") == "yes" else "COMPILED"
            else:
                tag = "FAILED"
            print(f"[{i}/{total}] {tag}: {res['FQN']}")

            with open(results_path, "a") as f:
                f.write(json.dumps(res, ensure_ascii=False) + "\n")
    finally:
        shutdown_repl_manager()

    # Summary
    with open(results_path) as f:
        all_results = [json.loads(l) for l in f if l.strip()]
    compiled = sum(1 for r in all_results if r.get("success"))
    eq_yes = sum(1 for r in all_results if r.get("success") and r.get("equivalence") == "yes")
    print(f"\nDone. {compiled}/{len(all_results)} compile, "
          f"{eq_yes}/{len(all_results)} also self-judged equivalent.")


if __name__ == "__main__":
    asyncio.run(main())
