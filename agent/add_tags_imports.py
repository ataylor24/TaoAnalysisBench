"""Post-hoc add `import Analysis.Tags.<Section>` lines to each relaxed entry,
matching the existing `import Analysis.<Section>` lines.

Skips any section that has no Tags/<Section>.lean module.
Writes a NEW jsonl alongside the input — never touches the original.
"""
import json
import re
from pathlib import Path

INPUT = Path('/Users/researcher/Desktop/lean_prover/src/agent/output/textbook_relaxed/results_stream.jsonl')
OUTPUT = INPUT.parent / 'results_stream_tagged.jsonl'
TAGS_DIR = Path('/Users/researcher/Desktop/lean_prover/analysis/analysis/Analysis/Tags')

# Sections that actually have a Tags module. Empty Appendices have none.
existing_tag_modules = {p.stem for p in TAGS_DIR.glob('*.lean')}
print(f'Found {len(existing_tag_modules)} Tags modules')

# Pattern: a top-of-file Analysis import (NOT already a Tags import).
ANALYSIS_IMPORT_RE = re.compile(r'^import Analysis\.([A-Za-z0-9_]+)\s*$')

def add_tags_imports(code: str) -> tuple[str, list[str]]:
    """Insert `import Analysis.Tags.<X>` after each `import Analysis.<X>`.
    Returns (new_code, [added_imports])."""
    added = []
    out_lines = []
    for line in code.splitlines():
        out_lines.append(line)
        m = ANALYSIS_IMPORT_RE.match(line)
        if not m:
            continue
        section = m.group(1)
        # Skip if already a Tags import.
        if section.startswith('Tags.'):
            continue
        if section not in existing_tag_modules:
            continue
        tag_import = f'import Analysis.Tags.{section}'
        out_lines.append(tag_import)
        added.append(tag_import)
    return '\n'.join(out_lines), added

# The relaxation results stream may have multiple rows per FQN (re-runs of
# previously-failed entries). Keep the LAST row per FQN.
latest: dict[str, dict] = {}
n_raw = 0
for ln in open(INPUT):
    if not ln.strip(): continue
    r = json.loads(ln)
    n_raw += 1
    fqn = r.get('FQN')
    if fqn:
        latest[fqn] = r
print(f'Raw lines in input: {n_raw}; unique FQNs: {len(latest)}')

n_total = 0
n_skipped_no_code = 0
n_with_imports = 0
n_added = 0
with open(OUTPUT, 'w') as fout:
    for r in latest.values():
        n_total += 1
        if not r.get('code'):
            r['tags_imports_added'] = []
            n_skipped_no_code += 1
        else:
            new_code, added = add_tags_imports(r['code'])
            if added:
                n_with_imports += 1
                n_added += len(added)
            r['code'] = new_code
            r['tags_imports_added'] = added
        fout.write(json.dumps(r, ensure_ascii=False) + '\n')

print(f'Processed {n_total} entries')
print(f'  {n_skipped_no_code} entries had no code (agent failed; passed through)')
print(f'  {n_with_imports} entries got at least one Tags import')
print(f'  {n_added} total Tags import lines added')
print(f'Wrote {OUTPUT}')
