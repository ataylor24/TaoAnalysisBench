"""LLM-curated attribute tagging for the Tao textbook (Option A).

For each Analysis section file, an agent reads the source and per-lemma
classifies it into one of the standard tactic-search rule sets:

    @[simp]                  — clean rewrite L = R / L ↔ R where L > R
    @[aesop safe]            — always succeeds, never worsens the goal
    @[aesop unsafe N]        — heuristic; may branch but useful
    (no tag)                 — default; conservative

Outputs one Lean module per section under
  analysis/analysis/Analysis/Tags/<section_name>.lean

Each Tags module imports its section and emits `attribute […] FQN` lines
for everything the agent decided to tag. Once these modules are built into
the Analysis package, downstream code (e.g., the relaxation agent's
output) can import both `Analysis.Section_5_6` AND
`Analysis.Tags.Section_5_6` to make `simp`/`aesop` reach textbook lemmas.

Usage:
    cd src/agent
    python tagging_workflow.py                         # tag all sections
    TAG_ONLY=Section_5_6 python tagging_workflow.py    # one section
    TAG_LIMIT=2 python tagging_workflow.py             # first N sections
"""
import dotenv
dotenv.load_dotenv()

import asyncio
import json
import os
import re
import subprocess
from pathlib import Path
# import weave  # optional tracing; pip install weave + uncomment
from agents import Agent, Runner, SQLiteSession, ModelSettings
from agents.exceptions import MaxTurnsExceeded
from openai.types.shared import Reasoning
# weave.init("...")  # optional tracing
# ── Configuration ──────────────────────────────────────────────────────
MAX_CONCURRENT = int(os.environ.get("TAG_CONCURRENT", "8"))
MAX_TURNS = int(os.environ.get("TAG_MAX_TURNS", "8"))
MODEL = os.environ.get("TAG_MODEL", "gpt-5.5-pro")

SOURCE_ROOT = Path(os.environ.get("ANALYSIS_BOOK_DIRECTORY", ""))
TAGS_DIR = SOURCE_ROOT / "Tags"
TAGS_DIR.mkdir(exist_ok=True)
RESULTS_DIR = Path("/Users/researcher/Desktop/lean_prover/src/agent/output/textbook_tags")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_PATH = RESULTS_DIR / "results_stream.jsonl"
LAKE_DIR = Path(os.environ.get("LEAN_RUNTIME", ""))
BUILD_VALIDATE_MAX_ITERS = 3
BUILD_VALIDATE_TIMEOUT = 180

# Serialize lake builds across concurrent sections — lake handles per-target
# locking but bunching them up just slows everyone down.
_BUILD_LOCK = asyncio.Lock()


# ── System prompt ──────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a Lean 4 attribute curator for tactic search.

Goal: for each named theorem/lemma/instance in a Tao Analysis textbook
section, decide which of `@[simp]`, `@[aesop safe]`, `@[aesop unsafe N%]`,
`@[grind]` to attach. Your output enables downstream solvers to use
`simp` / `aesop` / `grind` over the textbook's namespace, the way
Mathlib's tagged lemmas enable those tactics there.

There is NO default rule for tagging vs not-tagging. For each tag, only
attach it when one of its positive criteria below fires. If no tag's
criteria fire, emit `tags: []`. Multiple tags per declaration are fine
(e.g. `["simp", "grind"]` for an equational rewrite).

# Tag criteria

## `simp` — tag when ANY of:
- Equation `L = R` or iff `L ↔ R` with LHS structurally heavier than RHS
  (clear orientation, simp always reduces L → R)
- Closed-form simplification on a degenerate input
  (e.g. `f ∅ = …`, `f {x} = …`, `f 0 = …`)
- Definitional unfolding of a named wrapper/predicate into its body
  (e.g. `Real.Icc_def`, `Real.upperBound_def`)

## `simp` — SKIP when:
- Symmetric / non-orientable rewrite (would simp-loop)
- RHS introduces a free variable not bound on LHS (e.g. `a = a * 1` would
  rewrite under any `a`)
- LHS is structurally equal to or simpler than RHS (would rewrite the
  wrong way)
- Would obviously cycle with an existing commutativity/associativity simp
  lemma in Mathlib

## `aesop safe` — tag when ANY of:
- Forward closure fact: hypotheses easily discharged from typical context,
  conclusion strictly useful (e.g. `Bounded ∧ Nonempty → IsLUB E (sup E)`)
- Introduction lemma yielding the goal type from simpler pieces, with no
  free choice of witness
- Single-conclusion statement that doesn't commit to a specific branch
  or value

## `aesop safe` — SKIP when:
- Applying it commits to a specific witness (existence statements where
  `choose` would expose an arbitrary element)
- Consumes a useful hypothesis and produces a strictly weaker one
- Could fire on goals where it isn't actually the right step (e.g.
  rewrites that would run unconditionally on any `_ ∈ upperBounds E`)

## `aesop unsafe N%` — tag when ANY of:
- Useful but conditional or branching equality rewrite (direction not
  always right)
- Forward inference whose hypotheses can't always be discharged from
  context but is worth trying
- Deep theorem worth occasionally exploring during search

N% guidance:
  60-80%: rule almost always works when applicable
  30-50%: useful when context fits
  10-20%: deep theorem; aesop should rarely try it but may

## `grind` — pick a specific modifier per lemma (NEVER emit bare `grind`)

Lean's `grind` rejects bare `[grind]` for almost all non-trivial
statements; you MUST attach a modifier that matches the lemma's shape.
The accepted variants:

- `grind =` — clean equation `L = R` where both sides involve named
  (non-builtin) operators AND LHS is structurally heavier than RHS.
  Grind rewrites L → R deterministically. Best fit: definitional
  unfoldings like `Real.Icc_def : .Icc x y = { z | x ≤ z ∧ z ≤ y }`,
  closed-form values like `sup ∅ = ⊥`.

- `grind =_` — equation where neither side is clearly heavier; grind
  may chain in either direction. Use sparingly — risks loops.

- `grind →` — forward implication `H₁ → H₂ → … → C`. Tag when the
  conclusion `C` is unconditionally useful and hypotheses are typically
  available in context. Best fit: closure facts like
  `BddAbove E ∧ Nonempty E → IsLUB E (sup E)`.

- `grind ←` — backward (use the conclusion to look for proofs of the
  hypotheses). Rarely the right call; usually skip.

- `grind ext` — extensionality-shaped lemma like
  `f = g ↔ ∀ x, f x = g x` or `S = T ↔ ∀ x, x ∈ S ↔ x ∈ T`.
  Tag when it's the canonical way to reduce equality.

- `grind cases` — when the lemma's hypothesis is an inductive type
  that grind should automatically case-split on.

## `grind` — SKIP entirely when:
- Heavily quantified statement (multiple alternating ∀/∃) — would
  explode the E-graph
- Single-use internal proof helper
- None of the modifiers above is a clear fit (don't emit bare `grind`
  hoping it works — it will fail the build)

Tag string in JSON output is the full modifier-included form, e.g.
`"grind ="`, `"grind →"`, `"grind ext"` (NOT just `"grind"`).

# Output format

You receive the section source and a JSON list of all named declarations
in it (theorem / lemma / instance — definitions and structures aren't
tagged). For each declaration, emit ONE JSON object on its own line
inside a single ```json fence:

```json
{"fqn": "Chapter5.Real.Icc_def", "tags": ["simp", "grind ="]}
{"fqn": "Chapter5.Real.upperBound_def", "tags": ["simp"]}
{"fqn": "Chapter5.Real.exists_sup", "tags": []}
{"fqn": "Chapter5.Real.le_of_forall_lt_iff", "tags": ["aesop safe", "grind →"]}
{"fqn": "Chapter5.Real.LIM_abs", "tags": ["aesop unsafe 50%"]}
…
```

Every declaration in the input list MUST appear exactly once. Tags must
be lowercase strings exactly as they'd appear inside the brackets:
"simp", "aesop safe", "aesop unsafe 50%", "grind =", "grind →", etc.

No prose. One JSON object per line inside the ```json fence.
"""


Tagging_Agent = Agent(
    name="Textbook Tagging Agent",
    model=MODEL,
    instructions=SYSTEM_PROMPT,
    tools=[],
    model_settings=ModelSettings(reasoning=Reasoning(effort="high")),
)


CRITIQUE_PROMPT = """You are a Lean 4 attribute reviewer. You receive:
- A Tao Analysis textbook section's source
- The list of named declarations
- An initial set of tag decisions (post-build-validation; bad grind tags
  have already been stripped)

Your job: spot misjudgments and produce a REVISED tag set. Common
failure modes to look for:

1. WASTED REDUNDANCY: a lemma is tagged both `simp` AND `aesop unsafe N%`
   AND/OR `grind →` for the same conclusion. If `simp` already covers
   it, drop the redundant aesop/grind copies — they just add search noise.
   Only keep multiple tags when each tactic genuinely benefits.

2. MISSED MATHLIB-CANONICAL SIMPS: structural identities like
   `∑ (a + b) = ∑ a + ∑ b`, `c * ∑ a = ∑ (c * a)`, distributivity over
   named operators — these belong as `simp`. Mathlib treats analogous
   statements as simp. The first-pass tagger tends to be too cautious
   with these.

3. OVER-AGGRESSIVE `aesop safe`: a lemma whose hypotheses can NOT be
   easily discharged from typical context should not be `safe`. Demote
   to `aesop unsafe 30-50%`. Examples: deep theorems requiring a
   `Tendsto` or `Continuous` hypothesis per element.

4. UNDER-TAGGED OBVIOUS REWRITES: definitional unfoldings of named
   wrappers (`X_def : … = …` where one side is a single named symbol
   and the other its body) should be `simp` even if introducing
   existentials — the goal is to enable solver search.

5. RISKY `simp` ON IFF-DEFS: an iff-def that unwraps to a multi-conjunct
   existential (`BddAbove E ↔ ∃ M, …`) MAY flood goals. Consider
   whether keeping it as `simp` is worth the risk; demote to `grind →`
   if not.

6. POINTLESS DEEP-THEOREM TAGS: a theorem with 8+ hypotheses tagged
   `aesop unsafe 10%` will essentially never fire successfully (aesop
   tries it and immediately fails to discharge). If the hypothesis list
   is too long for aesop to plausibly close, drop the tag entirely.

# Hard guards (do NOT violate)

A. `simp` ONLY fires on equations (`L = R`) and iffs (`L ↔ R`). NEVER
   tag a Prop-valued statement that isn't an equation/iff with `simp`.
   Examples of statements that must NOT be tagged simp:
     - `(sup E).IsFinite`        (predicate, not equation)
     - `IsLUB E M`               (predicate, not equation)
     - `Set.Nonempty E`          (predicate, not equation)
     - `M ∈ upperBounds E`       (predicate, not equation — though
       the corresponding `_def` iff IS valid simp)
   simp tags on non-equational propositions are silent no-ops; tagging
   them is an error.

B. Do NOT demote `aesop safe` → `aesop unsafe` unless you can name a
   concrete goal shape where the rule would fire INCORRECTLY (i.e.
   produce a worse goal state, not just fail to fire). "Hypotheses
   might not be available" is NOT a valid reason to demote — aesop
   simply skips the rule when hypotheses aren't there. Demotion is for
   genuine harm (commits to wrong witness, loses information, etc.),
   not for hypothesis availability. When in doubt, KEEP `aesop safe`.

For each declaration, output the FINAL revised tags. You may keep tags
unchanged, add tags, remove tags, or change tag types. Tag syntax is
identical to the first pass:
  "simp", "aesop safe", "aesop unsafe N%",
  "grind =", "grind =_", "grind →", "grind ←", "grind ext", "grind cases"

NEVER emit a bare "grind" — Lean rejects it for non-trivial statements.

Output format: same as the first pass — one JSON object per declaration
on its own line inside a single ```json fence. Every declaration in the
input list MUST appear exactly once.

```json
{"fqn": "Chapter5.Real.Icc_def", "tags": ["simp"]}
{"fqn": "Chapter5.Real.LIM_abs", "tags": ["aesop unsafe 50%"]}
{"fqn": "Finset.finite_series_add", "tags": ["simp"]}
…
```

No prose outside the ```json fence.
"""


Critique_Agent = Agent(
    name="Textbook Tagging Critique Agent",
    model=MODEL,
    instructions=CRITIQUE_PROMPT,
    tools=[],
    model_settings=ModelSettings(reasoning=Reasoning(effort="high")),
)


# ── Helpers ────────────────────────────────────────────────────────────

# Match `theorem`/`lemma`/`instance` declarations and capture name.
# Robust to attributes, modifiers, and multi-line signatures (we just
# want the head line containing the keyword + name).
_DECL_RE = re.compile(
    r"^\s*(?:@\[[^\]]*\]\s*)*(?:noncomputable\s+|private\s+|protected\s+|partial\s+|opaque\s+)*"
    r"(theorem|lemma|instance)\s+(\S+)",
    re.MULTILINE,
)
_NS_OPEN_RE = re.compile(r"^\s*namespace\s+(\S+)", re.MULTILINE)
_NS_END_RE = re.compile(r"^\s*end\s+(\S+)", re.MULTILINE)


def parse_named_decls(source: str) -> list[dict]:
    """Walk the section source, tracking namespace stack, and return one
    entry per named theorem/lemma/instance: {fqn, kind, line}.

    Skips anonymous `example`s and any decl whose body is missing a sig
    (parser failure mode)."""
    out = []
    ns_stack: list[str] = []
    for line_no, line in enumerate(source.splitlines(), start=1):
        m = _NS_OPEN_RE.match(line)
        if m:
            ns_stack.append(m.group(1)); continue
        m = _NS_END_RE.match(line)
        if m:
            if ns_stack and ns_stack[-1] == m.group(1):
                ns_stack.pop()
            continue
        m = _DECL_RE.match(line)
        if m:
            kind, local = m.group(1), m.group(2)
            local = re.sub(r"\.\{[^}]*\}$", "", local)
            local = local.rstrip(":")  # `instance Foo: Bar where` (no space before colon)
            if local.startswith("_root_."):
                fqn = local[len("_root_."):]  # bypass namespace stack
            else:
                fqn = ".".join(ns_stack + [local]) if ns_stack else local
            out.append({"fqn": fqn, "kind": kind, "line": line_no})
    return out


def extract_json_block(text: str) -> str | None:
    m = re.search(r"```json\s*\n(.*?)```", text, re.DOTALL)
    return m.group(1).strip() if m else None


def parse_agent_output(text: str, expected_fqns: set[str]) -> tuple[dict[str, list[str]], list[str]]:
    """Parse the agent's JSON-fence output into {fqn: [tags]} and a list
    of warnings (missing FQNs, unknown FQNs, malformed lines)."""
    raw = extract_json_block(text) or text
    out: dict[str, list[str]] = {}
    warns: list[str] = []
    for ln in raw.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("//"): continue
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            warns.append(f"unparseable line: {ln[:80]!r}"); continue
        fqn = r.get("fqn")
        tags = r.get("tags") or []
        if not fqn:
            warns.append(f"row missing fqn: {ln[:80]!r}"); continue
        if not isinstance(tags, list):
            warns.append(f"{fqn}: tags not a list"); continue
        if fqn not in expected_fqns:
            warns.append(f"{fqn}: not in section's named-decl set"); continue
        out[fqn] = [str(t) for t in tags]
    missing = expected_fqns - set(out.keys())
    if missing:
        warns.append(f"{len(missing)} expected FQNs not classified (defaulting to untagged)")
        for fqn in missing:
            out[fqn] = []
    return out, warns


def _write_tags_with_line_map(
    section_name: str, tag_decisions: dict[str, list[str]]
) -> tuple[Path, dict[int, tuple[str, str]]]:
    """Write Analysis/Tags/<section>.lean and return (path, {1-indexed line:
    (fqn, tag)}) so build errors can be mapped back to the failing tag."""
    path = TAGS_DIR / f"{section_name}.lean"
    lines = [f"import Analysis.{section_name}", ""]
    line_to_tag: dict[int, tuple[str, str]] = {}
    n_tagged = 0
    for fqn, tags in sorted(tag_decisions.items()):
        if not tags: continue
        for t in tags:
            lines.append(f"attribute [{t}] {fqn}")
            line_to_tag[len(lines)] = (fqn, t)
            n_tagged += 1
    if n_tagged == 0:
        lines.append("-- (no attributes added)")
    path.write_text("\n".join(lines) + "\n")
    return path, line_to_tag


def write_tags_module(section_name: str, tag_decisions: dict[str, list[str]]) -> Path:
    path, _ = _write_tags_with_line_map(section_name, tag_decisions)
    return path


_BUILD_ERR_LINE_RE = re.compile(r"\.lean:(\d+):\d+:")


def _run_lake_build(section_name: str) -> tuple[int, str]:
    proc = subprocess.run(
        ["lake", "build", f"Analysis.Tags.{section_name}"],
        cwd=LAKE_DIR, capture_output=True, text=True, timeout=BUILD_VALIDATE_TIMEOUT,
    )
    return proc.returncode, (proc.stdout + "\n" + proc.stderr)


async def build_validate_and_strip(
    section_name: str, tag_decisions: dict[str, list[str]]
) -> tuple[Path, list[str], bool]:
    """Write the Tags file and `lake build` it. On failure, parse error line
    numbers, drop the offending attributes, rewrite, retry. Returns
    (path, dropped_lines_human_readable, build_succeeded)."""
    dropped: list[str] = []
    build_ok = False
    last_path: Path | None = None
    for it in range(BUILD_VALIDATE_MAX_ITERS):
        path, line_to_tag = _write_tags_with_line_map(section_name, tag_decisions)
        last_path = path
        async with _BUILD_LOCK:
            rc, output = await asyncio.to_thread(_run_lake_build, section_name)
        if rc == 0:
            build_ok = True
            break
        bad_lines = set()
        for ln in output.splitlines():
            if "error" not in ln.lower(): continue
            if f"Tags/{section_name}.lean:" not in ln: continue
            m = _BUILD_ERR_LINE_RE.search(ln)
            if m: bad_lines.add(int(m.group(1)))
        if not bad_lines:
            # Build failed but we couldn't pin it on a specific line; bail out.
            break
        # Strip the failing tags and loop.
        for ln_no in bad_lines:
            entry = line_to_tag.get(ln_no)
            if entry is None: continue
            fqn, tag = entry
            if fqn in tag_decisions and tag in tag_decisions[fqn]:
                tag_decisions[fqn] = [t for t in tag_decisions[fqn] if t != tag]
                dropped.append(f"[{tag}] {fqn}")
    assert last_path is not None
    return last_path, dropped, build_ok


# ── Per-section processing ─────────────────────────────────────────────

def build_query(section_name: str, source: str, decls: list[dict]) -> str:
    decl_list = "\n".join(f"  - {d['kind']:<8s}  {d['fqn']}" for d in decls)
    return f"""# Section: {section_name}

There are {len(decls)} named theorem/lemma/instance declarations in this
section. Classify each per the rules.

## Named declarations to classify

{decl_list}

## Full source

```lean
{source}
```

Emit one JSON line per declaration listed above (every FQN must appear
exactly once, tags as `[]` for untagged), inside a single ```json fence.
"""


def build_critique_query(
    section_name: str, source: str, decls: list[dict],
    initial_tags: dict[str, list[str]], dropped: list[str],
) -> str:
    """Build the input for the critique agent: same source + decl list,
    plus the first-pass tag decisions and any tags the validator stripped."""
    decl_lines = []
    for d in decls:
        ts = initial_tags.get(d["fqn"], [])
        ts_str = ", ".join(f'"{t}"' for t in ts) if ts else ""
        decl_lines.append(f"  - {d['kind']:<8s}  {d['fqn']:<60s}  [{ts_str}]")
    decl_block = "\n".join(decl_lines)
    dropped_block = (
        "\n".join(f"  - {d}" for d in dropped) if dropped
        else "  (none — all first-pass tags built cleanly)"
    )
    return f"""# Section: {section_name}

The first-pass tagger emitted decisions for {len(decls)} declarations.
The build-validator then stripped any tags Lean rejected. Below are the
decisions AS THEY STAND (post-stripping). Review them and produce a
revised tag set per the critique criteria.

## Named declarations + current tags

{decl_block}

## Tags the validator stripped from the first pass (already removed)

{dropped_block}

## Full source

```lean
{source}
```

Emit a revised JSON line per declaration (every FQN must appear exactly
once). Same format as the first pass — `[]` for untagged. Inside a
single ```json fence, no prose.
"""


async def process_section(idx: int, section_name: str, sem: asyncio.Semaphore) -> dict:
    async with sem:
        path = SOURCE_ROOT / f"{section_name}.lean"
        if not path.exists():
            return {"section": section_name, "status": "no_source", "error": str(path)}
        source = path.read_text()
        decls = parse_named_decls(source)
        if not decls:
            # Nothing to tag; still write an empty Tags module so the lib
            # has a uniform shape.
            tags_path = write_tags_module(section_name, {})
            return {"section": section_name, "status": "no_decls", "n_decls": 0,
                    "tags_path": str(tags_path)}

        query = build_query(section_name, source, decls)
        session = SQLiteSession(f"tagging_{idx}")
        agent_finished = False
        try:
            result = await Runner.run(
                Tagging_Agent, input=query, session=session, max_turns=MAX_TURNS,
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

        expected = set(d["fqn"] for d in decls)
        tags, warns = parse_agent_output(output_text or "", expected)
        tags_path, dropped, build_ok = await build_validate_and_strip(section_name, tags)
        if dropped:
            warns.append(
                f"build-validate dropped {len(dropped)} tag(s): "
                + ", ".join(dropped[:6]) + ("…" if len(dropped) > 6 else "")
            )
        if not build_ok:
            warns.append("Tags module STILL fails to build after stripping (first pass)")

        # ── Self-critique pass ─────────────────────────────────────────
        # Hand the post-validation tags back to a second agent for review,
        # then re-validate. Skip if the first pass's build is hopeless.
        if build_ok and os.environ.get("TAG_SKIP_CRITIQUE", "0") != "1":
            critique_query = build_critique_query(
                section_name, source, decls, tags, dropped
            )
            critique_session = SQLiteSession(f"tagging_critique_{idx}")
            critique_finished = False
            critique_text = ""
            try:
                cresult = await Runner.run(
                    Critique_Agent, input=critique_query,
                    session=critique_session, max_turns=MAX_TURNS,
                )
                critique_text = cresult.final_output
                critique_finished = True
                critique_error = None
            except MaxTurnsExceeded as e:
                critique_text = str(e)
                critique_error = {"type": "MaxTurnsExceeded", "message": str(e)}
            except Exception as e:
                critique_text = str(e)
                critique_error = {"type": type(e).__name__, "message": str(e)}

            if critique_finished:
                revised, rev_warns = parse_agent_output(critique_text or "", expected)
                rev_path, rev_dropped, rev_ok = await build_validate_and_strip(
                    section_name, revised
                )
                if rev_ok:
                    # Critique succeeded and built clean — adopt the revision.
                    n_added = sum(
                        1 for f in expected
                        if set(revised.get(f, [])) - set(tags.get(f, []))
                    )
                    n_removed = sum(
                        1 for f in expected
                        if set(tags.get(f, [])) - set(revised.get(f, []))
                    )
                    warns.append(
                        f"critique pass: {n_added} decl(s) gained tags, "
                        f"{n_removed} lost tags, "
                        f"{len(rev_dropped)} additional validator drops"
                    )
                    tags = revised
                    tags_path = rev_path
                    dropped = dropped + rev_dropped
                    build_ok = True
                    warns.extend(f"critique: {w}" for w in rev_warns)
                else:
                    warns.append(
                        "critique pass produced unbuildable tags; "
                        "keeping first-pass result"
                    )
            else:
                warns.append(
                    f"critique agent failed ({critique_error}); "
                    "keeping first-pass result"
                )

        # Tag-distribution counts (recomputed from final, post-strip tags)
        from collections import Counter
        tag_counts = Counter()
        for ts in tags.values():
            if not ts: tag_counts["(none)"] += 1
            for t in ts: tag_counts[t] += 1

        return {
            "section": section_name, "status": "ok" if build_ok else "build_failed",
            "n_decls": len(decls), "n_tagged": sum(1 for ts in tags.values() if ts),
            "n_dropped": len(dropped),
            "build_ok": build_ok,
            "tag_counts": dict(tag_counts),
            "warnings": warns[:20],
            "agent_finished": agent_finished, "run_error": run_error,
            "tags_path": str(tags_path),
        }


# ── Main ───────────────────────────────────────────────────────────────

async def main() -> None:
    sections = sorted(p.stem for p in SOURCE_ROOT.glob("Section_*.lean"))
    sections += sorted(p.stem for p in SOURCE_ROOT.glob("Appendix_*.lean"))
    print(f"Discovered {len(sections)} section files in {SOURCE_ROOT}")

    only_env = os.environ.get("TAG_ONLY", "").strip()
    if only_env:
        only = set(only_env.split(","))
        sections = [s for s in sections if s in only]
        print(f"Filtered to {len(sections)} via TAG_ONLY")

    limit = os.environ.get("TAG_LIMIT")
    if limit:
        sections = sections[: int(limit)]

    already_done = set()
    if RESULTS_PATH.exists():
        for ln in open(RESULTS_PATH):
            ln = ln.strip()
            if not ln: continue
            try:
                r = json.loads(ln)
                # Accept both successful and clean-no-decl outcomes; build_failed
                # entries are NOT skipped — we'll retry them on the next run.
                if r.get("status") in ("ok", "no_decls"):
                    already_done.add(r["section"])
            except json.JSONDecodeError:
                pass
    sections = [s for s in sections if s not in already_done]
    print(f"Already done: {len(already_done)} | To process: {len(sections)}")
    if not sections: return

    sem = asyncio.Semaphore(MAX_CONCURRENT)
    tasks = [process_section(i, s, sem) for i, s in enumerate(sections)]
    total = len(tasks)
    for i, coro in enumerate(asyncio.as_completed(tasks), start=1):
        res = await coro
        tag_summary = ", ".join(f"{k}={v}" for k, v in (res.get("tag_counts") or {}).items())
        dropped_note = f" [-{res.get('n_dropped',0)} dropped]" if res.get("n_dropped") else ""
        print(f"[{i}/{total}] {res['status']:13s} {res['section']:25s} "
              f"({res.get('n_decls','?')} decls, {res.get('n_tagged','?')} tagged{dropped_note}: {tag_summary})")
        with open(RESULTS_PATH, "a") as f:
            f.write(json.dumps(res, ensure_ascii=False) + "\n")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
