"""Relaxation agent — produce taobench_textbook_relaxed.jsonl entries.

For each target FQN: take the progenitor section's source, strip every
proven theorem/lemma/example body (keep the open-`sorry` ones and ALL
defs/abbrevs/instances/notation/etc.), force the target body to `:= by sorry`,
prepend `import Analysis.Section_X_Y` for each transitive dep section
(NOT the progenitor itself), strip ALL comments, and verify the result
compiles via the v4.26.0 REPL pool.

Why an agent rather than a script: classifying top-level declarations from
a Lean 4 source file is non-trivial (multi-line signatures, attributes,
nested namespaces, macros, body-spans-many-lines `by` blocks). The LLM does
this gracefully; REPL feedback catches mistakes.

Usage:
    cd src/agent
    python relaxation_workflow.py            # processes all entries
    RELAX_ONLY=Chapter5.Real.root_mul python relaxation_workflow.py
    RELAX_MAX_TURNS=15 python relaxation_workflow.py
"""
import dotenv
dotenv.load_dotenv()

import asyncio
import json
import os
import re
from pathlib import Path
# import weave  # optional tracing; pip install weave + uncomment
from agents import Agent, Runner, SQLiteSession, ModelSettings, function_tool
from agents.exceptions import MaxTurnsExceeded
from openai.types.shared import Reasoning

from toolchest.repl_pool import (
    compile_lean_file,
    compile_lean_file_string,
    initialize_repl_manager,
    shutdown_repl_manager,
)
from globals import OUTPUT_DIR
# weave.init("...")  # optional tracing
# ── Configuration ──────────────────────────────────────────────────────
MAX_CONCURRENT = int(os.environ.get("RELAX_CONCURRENT", "20"))
MAX_TURNS = int(os.environ.get("RELAX_MAX_TURNS", "15"))
MODEL = "gpt-5.5"
REPL_WORKSPACE = os.environ.get("LEAN_RUNTIME", "")
LEAN_VERSION = "leanprover/lean4:v4.26.0"
REPL_WORKERS = int(os.environ.get("REPL_WORKERS", "4"))

# Inputs we drive the agent over
DATASET_PATH = Path(os.environ.get(
    "RELAX_DATASET",
    "/Users/researcher/Desktop/lean_prover/src/agent/output/taobench_textbook_all.jsonl",
))
SOURCE_ROOT = Path(os.environ.get("ANALYSIS_BOOK_DIRECTORY", ""))
JIXIA_ROOT = Path(os.environ.get("JIXIA_DECL_DIR", ""))
# Authoritative FQN → file map maintained alongside the textbook.
BASELINE_INDEX_PATH = Path(os.environ.get("BASELINE_INDEX_PATH", ""))

RESULTS_DIR = Path(OUTPUT_DIR) / "textbook_relaxed"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_PATH = RESULTS_DIR / "results_stream.jsonl"


# ── Tools ──────────────────────────────────────────────────────────────

@function_tool
def compile_relaxed_code(code: str) -> str:
    """Compile a Lean 4 file (imports + decls + the target theorem) against
    Mathlib v4.26.0 + the Analysis package. Returns either a success message
    or a JSON-wrapped error report between LEAN_COMPILE_RESULT markers."""
    return compile_lean_file_string(code)


@function_tool
def read_section_file(section_name: str) -> str:
    """Return the full Lean source of a textbook section.

    section_name: name like "Section_5_6" or "Appendix_A_3" (no `.lean`).
    Returns the file contents, or an error string if the file is not found.
    """
    p = SOURCE_ROOT / f"{section_name}.lean"
    if not p.exists():
        return f"ERROR: section file {p} not found"
    return p.read_text()


# ── System prompt ──────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a Lean 4 source-code surgeon working inside Tao's Analysis textbook project at Lean v4.26.0 + Mathlib v4.26.0.

# Goal

Produce a "relaxed" minimal context for ONE target theorem. The output is a
single Lean 4 file that:

1. Imports Mathlib and the Analysis dependency sections (those LISTED in
   the user query — do NOT import the progenitor section that contains the
   target itself).
2. Inlines the progenitor section's source, with every proven
   theorem/lemma/example REMOVED (cheating risk via `exact?` etc.).
3. Includes the target theorem with body forced to `:= by sorry`.
4. COMPILES under the pinned Lean + Mathlib + Analysis environment.

# Hard rules

R1. Output ONLY a single Lean 4 file in one ```lean code block. No prose.

R2. STRIP ALL DOC COMMENTS AND NARRATIVE COMMENTS.
    Drop every `/-- … -/` docstring, every `/-! … -/` module string, every
    `/- … -/` block comment, and every `--` line comment from the source.
    The ONLY comments allowed in your output are the four MARKER comments
    described in R3 (and nothing else).

R3. STRUCTURAL MARKERS (mandatory). Insert exactly these four comment
    markers, in this order, each on its own line:

        -- <CONTEXT>
        ... all retained progenitor declarations ...
        -- </CONTEXT>
        -- <TARGET_THEOREM>
        theorem <Target.Name> ... := by
          sorry
        -- </TARGET_THEOREM>

    `<CONTEXT>` wraps the inlined progenitor declarations (the kept defs,
    instances, sorry-bodied theorems, etc.). `<TARGET_THEOREM>` wraps the
    target declaration. These four markers are the ONLY comments in the
    file.

    Place imports and `namespace …` lines BEFORE `-- <CONTEXT>`.
    Place the closing `end <Namespace>` AFTER `-- </TARGET_THEOREM>`.

R4. Imports: exactly `import Mathlib` plus `import Analysis.<dep>` for
    each dep listed in the query (and NOTHING ELSE). Sole permitted
    deviation: if `import Mathlib` triggers a destructive collision per
    the failure-recovery rule in step 4 below, swap it for
    `import Mathlib.Tactic`.

R5. KEEP AS MUCH CONTENT AS POSSIBLE. Specifically:

    R5a. KEEP VERBATIM (comments stripped per R2): every `def`, `abbrev`,
         `noncomputable def`, `structure`, `inductive`, `class`,
         `instance`, `notation`, `notation3`, `macro`, `macro_rules`,
         `syntax`, `open`, `open scoped`, `variable`, `universe`,
         `namespace`, `end`, `attribute` declaration. Keep section/
         namespace structure exactly as in the progenitor. These are
         substantive textbook content.

    R5b. KEEP THE STATEMENTS of every NAMED `theorem` / `lemma` that is
         NOT explicitly marked as an exercise (see R6), regardless of
         whether the source body was a real proof or `sorry`. Force the
         body to `:= by sorry` either way. Preserving the statement makes
         it available as a black-box fact for downstream search tactics
         (`exact?`, `apply?`); replacing the body with `sorry` removes any
         cheating-via-recall path.

R6. DROP these declarations entirely:

    R6a. Every anonymous `example` (no name → can't be referenced; pure
         noise).

    R6b. Every `theorem` / `lemma` whose preceding doc comment in the
         source identifies it as an exercise — e.g. `/-- Exercise 5.6.1 -/`,
         `/-- Exercise 7.1.1 (something) -/`, `/-- Lemma 5.6.6 (a) /
         Exercise 5.6.1 -/`. These are reader-facing problems analogous to
         the target; they don't belong in the surrounding context.

R7. The TARGET theorem (FQN given in the query) MUST appear in the output
    with body forced to `:= by\\n  sorry`, regardless of what its body was
    in the source. Place it at its original position in the section flow.
    Use the same `theorem`/`lemma` keyword as in the source.

R8. Do not add new declarations, helper definitions, or aliases. Do not
    rename anything.

# Workflow

1. Call read_section_file to get the progenitor source if you need to
   re-confirm the literal text. The user query will give you the source as
   well; prefer the tool when in doubt.

2. Walk top-level declarations in source order. Apply R4–R6.

3. Emit a candidate file (per R1–R3). Call compile_relaxed_code.

4. If compilation fails:
   - "unknown identifier" pointing at a removed theorem name → restore
     that theorem with body `:= by sorry` (its statement is a black-box
     fact a downstream user can lean on).
   - "unknown namespace" → check that you correctly emitted the
     `import Analysis.<dep>` lines AND the right `namespace …`/`open …`
     directives from the source.
   - syntax errors → almost always a partially-stripped declaration. Look
     near the reported line and re-emit cleanly.
   - typeclass synthesis errors → a `def`/`instance` was likely dropped
     by mistake; restore.
   - DESTRUCTIVE COLLISION between `import Mathlib` and the textbook's
     own redefinitions of core types (e.g. Chapter 2 redefining `Nat`'s
     `Add` instance, Chapter 3 redefining `Set`, Chapter 5 redefining
     `Real` from scratch). Symptoms: errors like
     `add_assoc has type … (@instHAdd ℕ instAdd) … but is expected to
     have type … (@instHAdd ℕ Nat.instAddMonoid…) …`, or `failed to
     synthesize OfNat <TextbookType> 0`, or repeated "ambiguous
     overload" / instance-resolution failures that no inlining-fix
     repairs. → fall back to `import Mathlib.Tactic` instead of
     `import Mathlib`. This keeps Mathlib's tactic library in scope but
     drops the heavy typeclass instances that conflict with the
     textbook's reconstructions.

5. When compilation succeeds, emit the FINAL file as your message in a
   single ```lean code block. No surrounding prose, no comments.
"""


Relaxation_Agent = Agent(
    name="Textbook Relaxation Agent",
    model=MODEL,
    instructions=SYSTEM_PROMPT,
    tools=[compile_relaxed_code, read_section_file],
    model_settings=ModelSettings(reasoning=Reasoning(effort="high")),
)


# ── Helpers ────────────────────────────────────────────────────────────

_MARKER_LINE_RE = re.compile(
    r"^\s*--\s*(<CONTEXT>|</CONTEXT>|<TARGET_THEOREM>|</TARGET_THEOREM>)\s*$"
)


def strip_non_marker_comments(text: str) -> str:
    """Remove every block comment (/- … -/ including /-- and /-!) and every
    -- line comment EXCEPT the four structural marker comments:
        -- <CONTEXT>      -- </CONTEXT>
        -- <TARGET_THEOREM>  -- </TARGET_THEOREM>
    Marker lines are preserved verbatim. Everything else gets stripped.
    Defensive post-processor — the agent should already follow R2/R3."""
    if not text:
        return text
    # First pass: drop block comments (greedy, nested-aware).
    out_chars = []
    i = 0
    n = len(text)
    while i < n:
        if text[i:i+2] == "/-":
            depth = 1
            j = i + 2
            while j < n and depth > 0:
                if text[j:j+2] == "/-":
                    depth += 1; j += 2
                elif text[j:j+2] == "-/":
                    depth -= 1; j += 2
                else:
                    j += 1
            i = j
            if i < n and text[i] == "\n":
                i += 1
            continue
        out_chars.append(text[i])
        i += 1
    no_block = "".join(out_chars)
    # Second pass: per-line, drop non-marker `--` lines and inline `--` tails.
    cleaned_lines = []
    for ln in no_block.splitlines():
        if _MARKER_LINE_RE.match(ln):
            cleaned_lines.append(ln)
            continue
        # Drop inline `-- …` tails (Lean's `--` comments run to EOL). Be
        # careful: `--` inside a string literal is technically possible
        # but extremely rare in this corpus, so we don't track strings.
        idx = ln.find("--")
        if idx >= 0:
            ln = ln[:idx].rstrip()
        cleaned_lines.append(ln)
    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


# Back-compat alias (older callers in the repo)
strip_all_comments = strip_non_marker_comments


_DECL_KEYWORDS = ('theorem', 'lemma', 'def', 'abbrev', 'instance', 'structure',
                  'inductive', 'class', 'axiom')

_DECL_RE = re.compile(
    r"^\s*(?:@\[[^\]]*\]\s*)*(?:noncomputable\s+|private\s+|protected\s+|partial\s+|opaque\s+)*"
    rf"(?:{'|'.join(_DECL_KEYWORDS)})\s+(\S+)"
)
_NS_OPEN_RE = re.compile(r"^\s*namespace\s+(\S+)")
_NS_END_RE = re.compile(r"^\s*end\s+(\S+)")
_IMPORT_RE = re.compile(r"^\s*import\s+Analysis\.(\S+)")


def index_textbook_sources(source_root: Path
                           ) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Walk every Analysis/Section_*.lean / Appendix_*.lean file once and build:
        fqn_to_section : {full FQN}              → section name (e.g. 'Section_5_6')
        section_imports: {section name}          → list of imported Analysis sub-modules

    Tracks the current `namespace … / end …` stack so an FQN combines the
    enclosing namespaces with the declaration name (which may itself be
    dotted, e.g. `theorem Real.add_comm` inside `namespace Chapter5`
    yields `Chapter5.Real.add_comm`).
    """
    fqn_to_section: dict[str, str] = {}
    section_imports: dict[str, list[str]] = {}
    files = list(source_root.glob("Section_*.lean")) + list(source_root.glob("Appendix_*.lean"))
    for path in files:
        section_name = path.stem
        try:
            text = path.read_text()
        except Exception:
            continue
        ns_stack: list[str] = []
        imports: list[str] = []
        for line in text.splitlines():
            m = _IMPORT_RE.match(line)
            if m:
                d = m.group(1)
                if d != section_name: imports.append(d)
                continue
            m = _NS_OPEN_RE.match(line)
            if m:
                ns_stack.append(m.group(1)); continue
            m = _NS_END_RE.match(line)
            if m:
                # Pop matching name from end of stack (Lean allows
                # `end Foo.Bar` for `namespace Foo.Bar`).
                name = m.group(1)
                if ns_stack and ns_stack[-1] == name:
                    ns_stack.pop()
                continue
            m = _DECL_RE.match(line)
            if m:
                local = m.group(1)
                # Strip universe params if present (e.g. `Foo.{u}` → `Foo`).
                local = re.sub(r"\.\{[^}]*\}$", "", local)
                full = ".".join(ns_stack + [local]) if ns_stack else local
                fqn_to_section[full] = section_name
        section_imports[section_name] = imports
    return fqn_to_section, section_imports


def load_baseline_index(path: Path) -> dict[str, str]:
    """Read teorth_analysis_exercises_strict_minimal.json into a
    {theorem_name → section_name} map. The baseline file uses the canonical
    short form for each theorem (`HasDerivWithinAt.of_smul`,
    `Exercise_8_5_4`, etc.) plus an explicit `file` path, so it's the
    authoritative cross-reference when the namespaced source-scan misses.
    """
    out: dict[str, str] = {}
    if not path.exists(): return out
    rows = json.load(open(path))
    for r in rows:
        name = r.get("theorem_name")
        f = r.get("file") or ""
        if not name or not f: continue
        # "Analysis/Section_10_1.lean" → "Section_10_1"
        section = Path(f).stem
        out[name] = section
    return out


def discover_dep_sections(fqn: str, fqn_to_section: dict,
                          section_imports: dict,
                          baseline_index: dict | None = None
                          ) -> tuple[str | None, list[str]]:
    """Return (progenitor_section, dep_sections) for an FQN.

    Resolution order for the progenitor:
      1. Full namespaced FQN match in the source-scan index.
      2. Strip leading `Chapter<N>.` and try again.
      3. Tail-name lookup in the baseline JSON (exact match).
      4. After-prefix-strip lookup in the baseline JSON.
    """
    prog = fqn_to_section.get(fqn)
    if not prog:
        # Try stripping leading `Chapter<N>.` from FQN
        parts = fqn.split('.', 1)
        if len(parts) > 1:
            prog = fqn_to_section.get(parts[1])
    if not prog and baseline_index:
        prog = baseline_index.get(fqn)
    if not prog and baseline_index:
        parts = fqn.split('.', 1)
        if len(parts) > 1:
            prog = baseline_index.get(parts[1])
    if not prog:
        return None, []
    return prog, list(section_imports.get(prog, []))


def extract_lean_block(text: str) -> str | None:
    """Pull the contents of the agent's `​`​`lean ... `​`​` fence."""
    if not text: return None
    m = re.search(r"```(?:lean4?|Lean4?)?\s*\n(.*?)```", text, re.DOTALL)
    return m.group(1).strip() if m else None


# ── Per-FQN spot-fix hints ─────────────────────────────────────────────
#
# Three FQNs in `taobench_textbook_all.jsonl` have known input-data issues
# that prevent the standard pipeline from resolving them. For each, we
# (a) override the progenitor + deps lookup, and (b) inject a hint into
# the agent's query explaining the discrepancy. Once the upstream input
# dataset is regenerated cleanly, this whole block can be deleted.

FQN_HINTS: dict[str, dict] = {
    "Chapter3.SetTheory.Set.card_eq_zero": {
        "progenitor_section": "Section_3_6",
        "dep_sections": ["Section_3_5"],
        "hint": (
            "DATA QUIRK — the dataset's FQN does NOT match a theorem in the "
            "live textbook source. The closest live theorem is "
            "`Chapter3.SetTheory.Set.empty_iff_card_eq_zero` (a related "
            "iff with extra hypothesis structure). For this entry, treat "
            "the dataset's signature as authoritative and emit the target "
            "exactly as:\n"
            "```lean\n"
            "theorem SetTheory.Set.card_eq_zero {X:Set} (hX: X.finite) :\n"
            "    X.card = 0 ↔ X = ∅ := by\n"
            "  sorry\n"
            "```\n"
            "Place it inside `namespace Chapter3` alongside the live "
            "`empty_iff_card_eq_zero` (do not REPLACE that theorem; the "
            "live theorem stays as a sibling sorry-stub per R5b)."
        ),
    },
    "Chapter11.Chapter7.Series.converges_qseries'": {
        "progenitor_section": "Section_11_9",
        # No deps — the theorem at top-level uses only Mathlib.
        "dep_sections": [],
        "hint": (
            "DATA QUIRK — the dataset's FQN incorrectly prefixes "
            "`Chapter11.`. The actual theorem in Section_11_9.lean is "
            "declared at TOP LEVEL of the file (after `end Chapter11` "
            "around line 237), so its real Lean FQN is just "
            "`Chapter7.Series.converges_qseries'`. Emit the target with "
            "that name (NOT `Chapter11.Chapter7.…`), placed after `end "
            "Chapter11`:\n"
            "```lean\n"
            "theorem Chapter7.Series.converges_qseries' (p:ℝ) :\n"
            "    (mk' (m := 1) fun n ↦ 1 / (n:ℝ) ^ p : Series).converges ↔ (p>1) := by\n"
            "  sorry\n"
            "```\n"
            "Keep its sibling top-level theorem `converges_qseries''` as "
            "a sorry-stub per R5b."
        ),
    },
    "Chapter11.Exercise_11_10_3": {
        "progenitor_section": "Section_11_10",
        "dep_sections": ["Section_9_6", "Section_10_3", "Section_11_9"],
        "hint": (
            "DATA QUIRK — the live source has this as an anonymous "
            "`example` (annotated `/-- Exercise 11.10.3-/`), NOT a named "
            "theorem. **Override R6a for this one entry**: instead of "
            "dropping the example, CONVERT it to a named theorem at the "
            "same source position:\n"
            "```lean\n"
            "theorem Exercise_11_10_3 {a b:ℝ} (hab: a < b) {f: ℝ → ℝ}\n"
            "    (hf: IntegrableOn f (Icc a b)) :\n"
            "    IntegrableOn (fun x ↦ f (-x)) (Icc (-b) (-a)) ∧\n"
            "    integ (fun x ↦ f (-x)) (Icc (-b) (-a)) = -integ f (Icc a b) := by\n"
            "  sorry\n"
            "```\n"
            "It must be inside `namespace Chapter11` so the resulting "
            "FQN is `Chapter11.Exercise_11_10_3`."
        ),
    },
}


# ── Per-FQN processing ─────────────────────────────────────────────────

def build_query(target_fqn: str, target_code_in_dataset: str,
                progenitor_section: str | None, dep_sections: list[str],
                progenitor_source: str, hint: str | None = None) -> str:
    deps_block = "\n".join(f"- Analysis.{s}" for s in dep_sections) or "(none)"
    hint_block = (
        f"\n# ⚠ SPOT-FIX HINT (input-data quirk)\n\n{hint}\n"
        if hint else ""
    )
    return f"""# Target

FQN: `{target_fqn}`
Progenitor section: `{progenitor_section}`

The target theorem's *current* minimal-context form (for reference only — the
real source for relaxation is the progenitor file shown below):

```lean
{target_code_in_dataset.strip()}
```

# Dep sections (already built; safe to import)

{deps_block}

# Progenitor source (full)

```lean
{progenitor_source}
```
{hint_block}
# Your task

Produce the relaxed file per the system rules:
- Strip the progenitor of every proven theorem/lemma/example
  (per R5; keep ones already `by sorry` per R6).
- Force target body to `:= by sorry`.
- Prepend `import Mathlib` and one `import Analysis.<dep>` per dep listed above.
- Strip ALL comments per R2.
- Verify it compiles via `compile_relaxed_code`.
- Emit the final file in one ```lean block, no prose.
"""


async def process_one(idx: int, entry: dict, sem: asyncio.Semaphore,
                      fqn_to_section: dict, section_imports: dict,
                      baseline_index: dict) -> dict:
    async with sem:
        fqn = entry.get("FQN")
        target_code = entry.get("code", "")

        # Spot-fix hint (input-data quirk overrides — see FQN_HINTS).
        hint_entry = FQN_HINTS.get(fqn)
        if hint_entry:
            progenitor = hint_entry["progenitor_section"]
            dep_sections = list(hint_entry["dep_sections"])
            hint_text = hint_entry["hint"]
        else:
            progenitor, dep_sections = discover_dep_sections(
                fqn, fqn_to_section, section_imports, baseline_index)
            hint_text = None
        if not progenitor:
            return {
                "FQN": fqn, "lean_version": LEAN_VERSION,
                "status": "no_progenitor",
                "error": f"FQN {fqn} not found in jixia decl index",
            }
        progenitor_path = SOURCE_ROOT / f"{progenitor}.lean"
        if not progenitor_path.exists():
            return {
                "FQN": fqn, "lean_version": LEAN_VERSION,
                "status": "no_source_file",
                "error": f"section file {progenitor_path} not found",
            }
        progenitor_source = progenitor_path.read_text()

        query = build_query(fqn, target_code, progenitor,
                            dep_sections, progenitor_source, hint=hint_text)
        session = SQLiteSession(f"relaxation_{idx}")

        agent_finished = False
        try:
            result = await Runner.run(
                Relaxation_Agent, input=query, session=session,
                max_turns=MAX_TURNS,
            )
            output_text = result.final_output
            agent_finished = True
            run_error = None
        except MaxTurnsExceeded as e:
            output_text = str(e)
            run_error = {"type": "MaxTurnsExceeded", "message": str(e)}
        except Exception as e:
            output_text = str(e)
            run_error = {"type": type(e).__name__, "message": str(e)}

        code = extract_lean_block(output_text or "") or ""
        # Defensive: drop any non-marker comments the agent left in.
        cleaned = strip_non_marker_comments(code) if code else ""

        compile_result = None
        success = False
        if cleaned:
            compile_result = await asyncio.to_thread(compile_lean_file, cleaned)
            success = bool(compile_result.get("success"))

        return {
            "FQN": fqn,
            "lean_version": LEAN_VERSION,
            "progenitor_section": progenitor,
            "dep_sections": dep_sections,
            "agent_finished": agent_finished,
            "success": success,
            "code": cleaned if cleaned else None,
            "compile_result": compile_result,
            "run_error": run_error,
            "raw_output": output_text if not success else None,
        }


# ── Main ───────────────────────────────────────────────────────────────

async def main() -> None:
    print(f"Indexing textbook sources from {SOURCE_ROOT}...")
    fqn_to_section, section_imports = index_textbook_sources(SOURCE_ROOT)
    print(f"  source scan: {len(fqn_to_section)} FQNs across {len(section_imports)} section files")
    baseline_index = load_baseline_index(BASELINE_INDEX_PATH)
    print(f"  baseline index: {len(baseline_index)} canonical theorem_name → section entries")

    with open(DATASET_PATH) as f:
        entries = [json.loads(l) for l in f if l.strip()]
    print(f"Dataset: {DATASET_PATH} ({len(entries)} entries)")

    only_env = os.environ.get("RELAX_ONLY", "").strip()
    only = set(only_env.split(",")) if only_env else None
    if only:
        entries = [e for e in entries if e.get("FQN") in only]
        print(f"Filtered to {len(entries)} via RELAX_ONLY")

    already_done = set()
    if RESULTS_PATH.exists():
        for line in open(RESULTS_PATH):
            line = line.strip()
            if not line: continue
            try:
                r = json.loads(line)
                if r.get("success"):
                    already_done.add(r["FQN"])
            except json.JSONDecodeError:
                pass
    entries = [e for e in entries if e.get("FQN") not in already_done]
    print(f"Already done: {len(already_done)} | To process: {len(entries)}")

    if not entries:
        print("Nothing to do.")
        return

    print(f"Booting REPL pool: workspace={REPL_WORKSPACE} workers={REPL_WORKERS}")
    initialize_repl_manager(REPL_WORKSPACE, REPL_WORKERS, verbose=False)
    try:
        sem = asyncio.Semaphore(MAX_CONCURRENT)
        tasks = [
            process_one(i, e, sem, fqn_to_section, section_imports, baseline_index)
            for i, e in enumerate(entries)
        ]
        total = len(tasks)
        for i, coro in enumerate(asyncio.as_completed(tasks), start=1):
            res = await coro
            tag = "OK" if res.get("success") else (res.get("status") or "FAIL")
            print(f"[{i}/{total}] {tag}: {res.get('FQN')}")
            with open(RESULTS_PATH, "a") as f:
                f.write(json.dumps(res, ensure_ascii=False) + "\n")
    finally:
        shutdown_repl_manager()

    rows = [json.loads(l) for l in open(RESULTS_PATH) if l.strip()]
    n_ok = sum(1 for r in rows if r.get("success"))
    print(f"\nDone. {n_ok}/{len(rows)} compile.")


if __name__ == "__main__":
    asyncio.run(main())
