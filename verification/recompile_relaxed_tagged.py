"""Compile each entry of results_stream_tagged.jsonl via the REPL pool to
verify the post-hoc Tags imports don't break compilation.

Outputs a side-by-side comparison with the original `success` field."""
import json
from pathlib import Path

from toolchest.repl_pool import (
    initialize_repl_manager, shutdown_repl_manager, compile_lean_file_string,
)

INPUT = Path('/Users/researcher/Desktop/lean_prover/src/agent/output/textbook_relaxed/results_stream_tagged.jsonl')
OUTPUT = INPUT.parent / 'results_stream_tagged_compiled.jsonl'
LEAN_DIR = os.environ.get("LEAN_RUNTIME", "")

initialize_repl_manager(lean_dir=LEAN_DIR, max_workers=4, verbose=False)

from concurrent.futures import ThreadPoolExecutor, as_completed

def compile_one(idx, r, total):
    if not r.get('code'):
        r['recompile_success'] = False
        r['recompile_errors'] = [{"data": "no code (agent failed)"}]
        r['recompile_skipped'] = True
        return idx, r, '(skip - no code)'
    result_str = compile_lean_file_string(r['code'])
    try:
        result = json.loads(result_str) if isinstance(result_str, str) else result_str
    except json.JSONDecodeError:
        result = {"raw": result_str}
    msgs = result.get('messages', []) if isinstance(result, dict) else []
    errors = [m for m in msgs if isinstance(m, dict) and m.get('severity') == 'error']
    r['recompile_success'] = (len(errors) == 0)
    r['recompile_errors'] = errors
    return idx, r, ''

try:
    rows = [json.loads(l) for l in open(INPUT) if l.strip()]
    print(f'Compiling {len(rows)} entries…')
    results = [None] * len(rows)
    completed = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(compile_one, i, r, len(rows)) for i, r in enumerate(rows)]
        for fut in as_completed(futures):
            idx, r, note = fut.result()
            results[idx] = r
            completed += 1
            new_ok = r.get('recompile_success')
            was_ok = r.get('success')
            marker = '✓' if new_ok else '✗'
            flip = ''
            if was_ok and not new_ok and not r.get('recompile_skipped'):
                flip = '  REGRESSION'
            elif (not was_ok) and new_ok:
                flip = '  IMPROVEMENT'
            if completed % 25 == 0 or flip or note:
                print(f'  [{completed:3d}/{len(rows)}] {marker} {r["FQN"]:60s} '
                      f'(was={was_ok}, now={new_ok}){flip} {note}')

    with open(OUTPUT, 'w') as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

    n_was_ok = sum(1 for r in results if r.get('success'))
    n_now_ok = sum(1 for r in results if r.get('recompile_success'))
    n_regress = sum(1 for r in results
                    if r.get('success') and not r.get('recompile_success')
                    and not r.get('recompile_skipped'))
    n_improve = sum(1 for r in results
                    if (not r.get('success')) and r.get('recompile_success'))
    print(f'\nSummary: was {n_was_ok}/{len(results)} passing, now {n_now_ok}/{len(results)} passing')
    print(f'  Regressions (passed before, fail now): {n_regress}')
    print(f'  Improvements (failed before, pass now): {n_improve}')
    print(f'Wrote {OUTPUT}')
finally:
    shutdown_repl_manager()
