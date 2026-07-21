"""Verify model-inference proof attempts against the taobench datasets.

Pipeline per inference row:
  1. Look up the canonical Lean slice (the "minimal environment") in the
     dataset by FQN. This contains the imports, namespaces, helper definitions,
     and the target declaration ending in `:= by sorry`.
  2. Extract the proof body from the model's answer field. Robust to common
     packagings: markdown ```lean fences, full theorem-with-proof rewrites, or
     bare tactic blocks.
  3. Splice the extracted proof into the canonical slice, replacing the LAST
     `:= by sorry` (or `:= by\\n  sorry`) with `:= by\\n  <proof>`.
  4. Send the resulting whole file to the REPL pool at v4.26.0 and record
     compile success / first error.

Usage:
    python verify_inference.py \\
        --workspace /path/to/repl_v4.26.0 \\
        --dataset   /path/to/taobench_textbook_all.jsonl \\
        --inference /path/to/your_model_inferences.jsonl \\
        --output    /path/to/verify_results.jsonl \\
        --workers 4

Inference JSONL row schema (any of the following field names accepted):
    {"FQN": "Chapter5.Real.add_comm",
     "answer": "<the model's full text answer>"}
  or
    {"FQN": "...", "proof": "<just the tactic block>"}
  or
    {"FQN": "...", "code": "<full Lean file the model rewrote>"}

The script tries `code` → `answer` → `proof` in that order.

Output JSONL row schema (one row per inference attempt):
    {"FQN": "...",
     "success": bool,
     "error": str|None,
     "first_error_line": int|None,
     "lean_version": "leanprover/lean4:v4.26.0",
     "extracted_proof": "<what we extracted, for debugging>",
     "spliced_code": "<full code we sent to the compiler, for debugging>"}

Resumes by skipping any FQN already present in --output.
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

THIS = Path(__file__).resolve().parent
# repl_pool harness expected at ./harness/ (or pass --harness <dir>)
DEFAULT_HARNESS = THIS / "harness"


# ────────────────────────────────────────────────────────────────────────
# Proof extraction
# ────────────────────────────────────────────────────────────────────────

_FENCE_RE = re.compile(r"```(?:lean4?|Lean4?)?\s*\n(.*?)```", re.DOTALL)
_DECL_HEADER_RE = re.compile(
    r"^\s*(?:noncomputable\s+|private\s+|protected\s+|partial\s+|opaque\s+|@\[[^\]]*\]\s*)*"
    r"\b(?:theorem|lemma|example|def|abbrev|instance|class|structure|inductive)\b",
    re.MULTILINE,
)


def extract_proof(answer: str) -> str:
    """Pull a tactic block out of the model's answer.

    Strategy:
      1. If answer contains a ```lean fence, take the contents.
      2. If the contents start with a Lean declaration keyword (theorem/etc.),
         strip down to the proof body after the LAST `:= by`.
      3. Otherwise, treat the whole text as raw tactics.
    Always strip leading/trailing whitespace.
    """
    if not answer:
        return ""

    # 1. Fenced code block
    m = _FENCE_RE.search(answer)
    text = m.group(1) if m else answer

    # 2. Full declaration → strip down to body after last `:= by`
    if _DECL_HEADER_RE.search(text):
        # Find the LAST `:= by` (some files have nested `by` blocks; the
        # outermost is the proof of the top-level declaration). Then take
        # everything after, stripping trailing `end <ns>` lines.
        last_by = None
        for m_by in re.finditer(r":=\s*by\b", text):
            last_by = m_by
        if last_by is not None:
            tail = text[last_by.end():]
            # Drop trailing namespace/end lines (named or bare).
            tail = re.sub(r"(?m)^\s*end(?:\s+\S+)?\s*$", "", tail)
            return tail.strip()

    return text.strip()


# ────────────────────────────────────────────────────────────────────────
# Splice into the canonical slice
# ────────────────────────────────────────────────────────────────────────

# Match `:= by sorry` (single-line) OR `:= by\n  sorry` (multi-line),
# allowing optional whitespace and trailing comment. Capture the indent of
# the `by` keyword so the substitute can mirror it.
_SORRY_RE = re.compile(
    r":=(\s*)by(\s*)\bsorry\b",
)


def splice_proof_into_slice(slice_code: str, proof: str) -> tuple[str, bool]:
    """Replace the LAST `:= by sorry` in slice_code with `:= by <proof>`.

    Returns (spliced_code, did_splice). If no `:= by sorry` is found (e.g.,
    the slice's target uses a different sorry pattern), `did_splice` is False
    and the caller should treat that as a verification error.
    """
    # Find all matches; we replace the last one.
    matches = list(_SORRY_RE.finditer(slice_code))
    if not matches:
        return slice_code, False
    last = matches[-1]

    # Indent the proof body by 2 spaces (or detect existing indent if multi-line).
    proof_lines = proof.strip().splitlines()
    if not proof_lines:
        # Empty proof — leave the sorry in place to make the failure obvious.
        return slice_code, False

    if len(proof_lines) == 1:
        # Single-line tactic. Inline it: `:= by <tactic>`.
        replacement = f":= by {proof_lines[0]}"
    else:
        # Multi-line: place tactics on their own line, indented by 2 spaces
        # relative to the `:= by`. Lean's tactic mode requires the body to
        # be indented strictly more than the `by` token's column.
        # Use 2-space indent as the canonical convention.
        body = "\n".join("  " + ln if ln.strip() else ln for ln in proof_lines)
        replacement = f":= by\n{body}"

    return slice_code[:last.start()] + replacement + slice_code[last.end():], True


# ────────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────────

def load_inferences(path: Path) -> list[dict]:
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            rows.append(r)
    return rows


def get_inference_text(row: dict) -> str:
    """Pull the model's answer from the row, trying common field names."""
    for fld in ("code", "answer", "proof", "output", "completion", "response"):
        if row.get(fld):
            return row[fld]
    return ""


def load_done(output_path: Path) -> set[str]:
    if not output_path.exists():
        return set()
    done = set()
    with output_path.open() as f:
        for line in f:
            try:
                done.add(json.loads(line)["FQN"])
            except (json.JSONDecodeError, KeyError):
                pass
    return done


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--workspace", required=True, help="Lake workspace dir (lean-toolchain + lakefile)")
    p.add_argument("--dataset", required=True, help="Path to taobench_{textbook,mathlib}_all.jsonl")
    p.add_argument("--inference", required=True, help="Model inference JSONL")
    p.add_argument("--output", required=True, help="Verification results JSONL")
    p.add_argument("--harness", default=str(DEFAULT_HARNESS), help="Path to repl_pool harness dir")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--timeout", type=float, default=180.0, help="Per-file compile timeout (s)")
    p.add_argument("--init-timeout", type=float, default=600.0, help="REPL boot timeout (s)")
    p.add_argument("--limit", type=int, default=None, help="Only verify N rows")
    p.add_argument("--only", default=None, help="Comma-separated FQNs to verify")
    p.add_argument("--debug-keep-spliced", action="store_true",
                   help="Include the spliced source in each output row (default: only on failure)")
    args = p.parse_args()

    sys.path.insert(0, args.harness)
    from simple_worker import LeanREPLSimpleWorker  # noqa: E402

    workspace = Path(args.workspace).resolve()
    if not (workspace / "lean-toolchain").exists():
        sys.exit(f"Workspace missing lean-toolchain: {workspace}")
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lean_version = (workspace / "lean-toolchain").read_text().strip()

    # Load dataset
    dataset = {}
    with open(args.dataset) as f:
        for line in f:
            if not line.strip(): continue
            r = json.loads(line)
            dataset[r["FQN"]] = r
    print(f"Workspace:     {workspace}")
    print(f"Lean toolchain:{lean_version}")
    print(f"Dataset:       {args.dataset} ({len(dataset)} canonical entries)")

    # Load inferences
    inferences = load_inferences(Path(args.inference))
    print(f"Inferences:    {args.inference} ({len(inferences)} rows)")

    only = set(args.only.split(",")) if args.only else None
    if only:
        inferences = [r for r in inferences if r.get("FQN") in only]
        print(f"  Filtered to {len(inferences)} via --only")

    done = load_done(output_path)
    inferences = [r for r in inferences if r.get("FQN") not in done]
    print(f"  Already done: {len(done)} | To verify: {len(inferences)}")

    if args.limit:
        inferences = inferences[: args.limit]
        print(f"  Limiting to {len(inferences)}")

    if not inferences:
        print("Nothing to do.")
        return

    # Boot worker pool
    print(f"Booting {args.workers} REPL workers...")
    t0 = time.time()
    workers: list = []

    def boot(i: int):
        w = LeanREPLSimpleWorker(lean_dir=str(workspace), worker_id=i, verbose=False)
        w.start(timeout=args.init_timeout)
        return w

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(boot, i) for i in range(args.workers)]
        for fut in as_completed(futs):
            try:
                workers.append(fut.result())
            except Exception as e:
                print(f"  Worker boot failed: {e}")
    print(f"  Booted {len(workers)}/{args.workers} workers in {time.time() - t0:.1f}s")
    if not workers:
        sys.exit("No workers available")

    pool: queue.Queue = queue.Queue()
    for w in workers:
        pool.put(w)

    out_lock = threading.Lock()
    counter_lock = threading.Lock()
    progress = {"i": 0}
    counts = {"ok": 0, "fail": 0, "skip": 0}

    def verify_one(inf_row: dict) -> dict:
        fqn = inf_row.get("FQN", "")
        canon = dataset.get(fqn)
        if canon is None:
            return {"FQN": fqn, "success": False, "error": "FQN not in dataset",
                    "lean_version": lean_version, "phase": "lookup"}

        proof = extract_proof(get_inference_text(inf_row))
        if not proof:
            return {"FQN": fqn, "success": False, "error": "empty proof from inference",
                    "lean_version": lean_version, "phase": "extract",
                    "extracted_proof": ""}

        spliced, ok = splice_proof_into_slice(canon["code"], proof)
        if not ok:
            return {"FQN": fqn, "success": False, "error": "no `:= by sorry` to splice into",
                    "lean_version": lean_version, "phase": "splice",
                    "extracted_proof": proof}

        # Strip top-level `import` lines — REPL workers have Mathlib pre-loaded
        # in their base env. Keeping them would re-import which is illegal at
        # non-zero env.
        stripped = "\n".join(
            ln for ln in spliced.splitlines() if not re.match(r"\s*import\s+\S", ln)
        )

        worker = pool.get()
        try:
            try:
                res, _ = worker._send_command(
                    {"cmd": stripped, "env": worker.base_env}, timeout=args.timeout
                )
            except Exception as e:
                return {"FQN": fqn, "success": False, "error": f"{type(e).__name__}: {e}",
                        "lean_version": lean_version, "phase": "send",
                        "extracted_proof": proof,
                        "spliced_code": spliced if args.debug_keep_spliced else None}

            messages = res.get("messages", []) or []
            if "error" in res:
                err = res["error"]
                return {"FQN": fqn, "success": False, "error": err,
                        "lean_version": lean_version, "phase": "compile",
                        "extracted_proof": proof,
                        "spliced_code": spliced}
            errors = [m for m in messages if m.get("severity") == "error"]
            if errors:
                first = errors[0]
                return {"FQN": fqn, "success": False, "error": first.get("data", "<no data>"),
                        "first_error_line": (first.get("pos") or {}).get("line"),
                        "lean_version": lean_version, "phase": "compile",
                        "extracted_proof": proof,
                        "spliced_code": spliced}
            return {"FQN": fqn, "success": True, "error": None,
                    "lean_version": lean_version,
                    "extracted_proof": proof,
                    "spliced_code": spliced if args.debug_keep_spliced else None}
        finally:
            # Recycle worker if process is dead
            if worker.proc is None or worker.proc.poll() is not None:
                try:
                    worker.kill()
                except Exception:
                    pass
                try:
                    worker.start(timeout=args.init_timeout)
                except Exception as e:
                    print(f"  Worker {worker.worker_id} failed to restart: {e}")
            pool.put(worker)

    total = len(inferences)
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(verify_one, r): r for r in inferences}
        for fut in as_completed(futs):
            try:
                out = fut.result()
            except Exception as e:
                inf = futs[fut]
                out = {"FQN": inf.get("FQN"), "success": False,
                       "error": f"{type(e).__name__}: {e}",
                       "lean_version": lean_version, "phase": "executor"}
            tag = "OK" if out["success"] else "FAIL"
            counts["ok" if out["success"] else "fail"] += 1
            with counter_lock:
                progress["i"] += 1
                idx = progress["i"]
            with out_lock:
                with output_path.open("a") as f:
                    f.write(json.dumps(out, ensure_ascii=False) + "\n")
            print(f"[{idx}/{total}] {tag}: {out['FQN']}")

    for w in workers:
        try:
            w.kill()
        except Exception:
            pass

    print()
    print(f"Done: {counts['ok']} OK, {counts['fail']} FAIL")


if __name__ == "__main__":
    main()
