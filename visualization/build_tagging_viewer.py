"""Build the tagging-smoke-test viewer from generated Tags modules + sources."""
import json
import re
from pathlib import Path

ANALYSIS_ROOT = Path(os.environ.get("ANALYSIS_BOOK_DIRECTORY", ""))
TAGS_DIR = ANALYSIS_ROOT / 'Tags'
RESULTS = Path('/Users/researcher/Desktop/lean_prover/src/agent/output/textbook_tags/results_stream.jsonl')
OUT = Path('/Users/researcher/Desktop/lean_prover/proof_analysis/tagging_viewer.html')

# ── Parse a Tags file into {fqn: [tags]} ───────────────────────────────
ATTR_RE = re.compile(r'^\s*attribute\s+\[([^\]]+)\]\s+(\S+)\s*$')

def parse_tags_file(path: Path) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        m = ATTR_RE.match(line)
        if not m: continue
        tag, fqn = m.group(1).strip(), m.group(2).strip()
        out.setdefault(fqn, []).append(tag)
    return out

# ── Parse named decls in a section source (mirrors tagging_workflow.parse_named_decls) ──
_DECL_RE = re.compile(
    r"^\s*(?:@\[[^\]]*\]\s*)*(?:noncomputable\s+|private\s+|protected\s+|partial\s+|opaque\s+)*"
    r"(theorem|lemma|instance)\s+(\S+)"
)
_NS_OPEN_RE = re.compile(r"^\s*namespace\s+(\S+)")
_NS_END_RE = re.compile(r"^\s*end\s+(\S+)")

def parse_named_decls(source: str) -> list[dict]:
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
            local = local.rstrip(":")
            if local.startswith("_root_."):
                fqn = local[len("_root_."):]
                local_display = local[len("_root_."):]
            else:
                fqn = ".".join(ns_stack + [local]) if ns_stack else local
                local_display = local
            out.append({"fqn": fqn, "kind": kind, "line": line_no, "local": local_display})
    return out

# ── Build entries ──────────────────────────────────────────────────────
results_by_section = {}
if RESULTS.exists():
    for ln in RESULTS.read_text().splitlines():
        if not ln.strip(): continue
        r = json.loads(ln)
        results_by_section[r['section']] = r

entries = []
for section_path in sorted(TAGS_DIR.glob('Section_*.lean')) + sorted(TAGS_DIR.glob('Appendix_*.lean')):
    section = section_path.stem
    src_path = ANALYSIS_ROOT / f'{section}.lean'
    if not src_path.exists():
        continue
    source = src_path.read_text()
    decls = parse_named_decls(source)
    tags = parse_tags_file(section_path)
    decl_records = []
    for d in decls:
        decl_records.append({
            'fqn': d['fqn'],
            'local': d['local'],
            'kind': d['kind'],
            'line': d['line'],
            'tags': tags.get(d['fqn'], []),
        })
    res = results_by_section.get(section, {})
    entries.append({
        'section': section,
        'source': source,
        'decls': decl_records,
        'n_decls': len(decls),
        'n_tagged': sum(1 for d in decl_records if d['tags']),
        'tag_counts': res.get('tag_counts', {}),
        'warnings': res.get('warnings', []),
        'agent_finished': res.get('agent_finished'),
    })

PLACEHOLDER = "__ENTRIES_JSON_PLACEHOLDER__"

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>taobench textbook tagging — smoke viewer</title>
<style>
  :root {
    --bg: #14161d; --fg: #e3e6ec; --muted: #8b8f97; --border: #2a2e3a;
    --sidebar-bg: #1a1d24; --code-bg: #0f1117; --code-fg: #e5e7eb;
    --keyword: #d29ad2; --type: #6dc7e6; --string: #b3d9a3;
    --number: #f4ad75; --punct: #9aa0a6; --comment: #6b7280;
    --accent: #6ea2ff;
    --simp-bg: rgba(155, 229, 155, 0.20); --simp-fg: #9be59b;
    --safe-bg: rgba(110, 162, 255, 0.22); --safe-fg: #9bbeff;
    --unsafe-bg: rgba(244, 173, 117, 0.22); --unsafe-fg: #f4ad75;
    --grind-bg: rgba(210, 154, 210, 0.22); --grind-fg: #d29ad2;
    --untag-bg: rgba(139, 143, 151, 0.18); --untag-fg: #b1b6c0;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; height: 100%; font-family: -apple-system, BlinkMacSystemFont, 'Inter', sans-serif; background: var(--bg); color: var(--fg); }
  .layout { display: grid; grid-template-columns: 240px 1fr 360px; height: 100vh; }
  aside.left { background: var(--sidebar-bg); border-right: 1px solid var(--border); overflow-y: auto; padding: 12px; }
  aside.right { background: var(--sidebar-bg); border-left: 1px solid var(--border); overflow-y: auto; padding: 16px; }
  aside h1 { font-size: 12px; margin: 6px 8px 12px 8px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
  .entry-link { display: block; padding: 8px 10px; margin-bottom: 4px; border-radius: 6px; cursor: pointer; font-family: 'JetBrains Mono', 'SF Mono', Menlo, monospace; font-size: 12px; color: var(--fg); border: 1px solid transparent; }
  .entry-link:hover { background: rgba(127,127,127,0.15); }
  .entry-link.active { background: var(--accent); color: white; border-color: var(--accent); }
  .entry-link .name { display: block; margin-bottom: 4px; font-weight: 600; }
  .entry-link .meta { display: flex; gap: 6px; font-size: 10px; color: var(--muted); flex-wrap: wrap; }
  .entry-link.active .meta { color: rgba(255,255,255,0.85); }
  main { overflow-y: auto; padding: 24px 32px; }
  header { margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid var(--border); }
  header h2 { margin: 0 0 6px 0; font-family: 'JetBrains Mono', 'SF Mono', Menlo, monospace; font-size: 18px; }
  header .meta-row { display: flex; gap: 16px; flex-wrap: wrap; font-size: 12px; color: var(--muted); margin-top: 6px; }
  header .meta-row .label { color: var(--fg); font-weight: 600; }
  .legend { display: flex; gap: 10px; margin-top: 10px; flex-wrap: wrap; align-items: center; }
  .legend .filter { cursor: pointer; user-select: none; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-family: 'JetBrains Mono', 'SF Mono', Menlo, monospace; border: 1px solid transparent; }
  .legend .filter.off { opacity: 0.35; }
  .pill { display: inline-block; padding: 1px 6px; border-radius: 999px; font-size: 10px; line-height: 1.5; font-weight: 600; font-family: 'JetBrains Mono', 'SF Mono', Menlo, monospace; }
  .pill.simp { background: var(--simp-bg); color: var(--simp-fg); }
  .pill.safe { background: var(--safe-bg); color: var(--safe-fg); }
  .pill.unsafe { background: var(--unsafe-bg); color: var(--unsafe-fg); }
  .pill.grind { background: var(--grind-bg); color: var(--grind-fg); }
  .pill.untag { background: var(--untag-bg); color: var(--untag-fg); }
  .code-block { background: var(--code-bg); color: var(--code-fg); border-radius: 8px; padding: 16px; overflow-x: auto; font-family: 'JetBrains Mono', 'SF Mono', Menlo, monospace; font-size: 13px; line-height: 1.55; }
  .code-line { display: block; white-space: pre; padding-left: 4px; border-left: 3px solid transparent; }
  .code-line .ln { display: inline-block; width: 3em; color: #6b7280; user-select: none; text-align: right; padding-right: 1em; opacity: 0.6; }
  .code-line.tagged-simp   { background: rgba(155, 229, 155, 0.07); border-left-color: var(--simp-fg); }
  .code-line.tagged-safe   { background: rgba(110, 162, 255, 0.07); border-left-color: var(--safe-fg); }
  .code-line.tagged-unsafe { background: rgba(244, 173, 117, 0.07); border-left-color: var(--unsafe-fg); }
  .code-line.tagged-grind  { background: rgba(210, 154, 210, 0.07); border-left-color: var(--grind-fg); }
  .code-line.tagged-multi  { background: rgba(120, 200, 200, 0.10); border-left-color: #9be0e0; }
  .code-line.tagged-untag  { border-left-color: rgba(139, 143, 151, 0.4); }
  .code-line .inline-tag { float: right; margin-left: 12px; font-size: 10px; opacity: 0.95; }
  .keyword { color: var(--keyword); }
  .type    { color: var(--type); }
  .string  { color: var(--string); }
  .number  { color: var(--number); }
  .punct   { color: var(--punct); }
  .comment { color: var(--comment); font-style: italic; }
  aside.right h3 { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; margin: 16px 0 8px 0; }
  aside.right h3:first-child { margin-top: 0; }
  .stat-block { background: var(--code-bg); border-radius: 6px; padding: 10px 12px; font-family: 'JetBrains Mono', 'SF Mono', Menlo, monospace; font-size: 11px; }
  .stat-block .row { display: flex; justify-content: space-between; padding: 2px 0; }
  .stat-block .row .v { font-weight: 600; }
  .decl-row { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 4px 6px; border-radius: 4px; cursor: pointer; font-family: 'JetBrains Mono', 'SF Mono', Menlo, monospace; font-size: 11px; }
  .decl-row:hover { background: rgba(127,127,127,0.12); }
  .decl-row .name { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1; }
  .warn { color: #f5b1b1; font-size: 11px; padding: 6px 10px; background: rgba(75, 26, 26, 0.5); border-radius: 4px; margin-top: 6px; font-family: 'JetBrains Mono', 'SF Mono', Menlo, monospace; }
</style>
</head>
<body>
<div class="layout">
  <aside class="left">
    <h1>Sections</h1>
    <div id="sidebar"></div>
  </aside>
  <main>
    <header>
      <h2 id="hdr-section"></h2>
      <div class="meta-row">
        <div><span class="label">decls:</span> <span id="hdr-ndecls"></span></div>
        <div><span class="label">tagged:</span> <span id="hdr-ntagged"></span></div>
        <div><span class="label">agent:</span> <span id="hdr-agent"></span></div>
      </div>
      <div class="legend" id="legend">
        <span class="filter pill simp" data-tag="simp">simp</span>
        <span class="filter pill safe" data-tag="safe">aesop safe</span>
        <span class="filter pill unsafe" data-tag="unsafe">aesop unsafe</span>
        <span class="filter pill grind" data-tag="grind">grind</span>
        <span class="filter pill untag" data-tag="untag">(untagged)</span>
      </div>
    </header>
    <div class="code-block" id="code"></div>
  </main>
  <aside class="right">
    <h3>Tag distribution</h3>
    <div class="stat-block" id="stats"></div>
    <h3>Tagged declarations</h3>
    <div id="tagged-list"></div>
    <h3>Untagged declarations</h3>
    <div id="untagged-list"></div>
    <h3>Warnings</h3>
    <div id="warnings"></div>
  </aside>
</div>
<script>
const ENTRIES = __ENTRIES_JSON_PLACEHOLDER__;
let currentIdx = 0;
const filterState = { simp: true, safe: true, unsafe: true, grind: true, untag: true };

const KEYWORDS = new Set([
  'import','open','namespace','end','section','variable','universe','universes',
  'theorem','lemma','example','def','abbrev','noncomputable','partial','opaque',
  'structure','inductive','class','instance','where','extends','attribute',
  'fun','let','if','then','else','match','with','have','show','from','by','sorry','admit',
  'intro','intros','exact','refine','apply','rfl','rw','simp','aesop','linarith','omega',
  'cases','rcases','obtain','induction','constructor','exfalso','contradiction',
  'forall','exists','True','False','Prop','Type','Sort',
  'private','protected','scoped','syntax','macro','macro_rules','notation','notation3',
  'do','return','in','at','using','calc','axiom'
]);

function escapeHtml(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}

function highlight(line) {
  let out = '';
  let i = 0;
  const n = line.length;
  while (i < n) {
    const c = line[i];
    if (c === '"') {
      let j = i+1;
      while (j < n && line[j] !== '"') { if (line[j]==='\\\\') j++; j++; }
      j = Math.min(n, j+1);
      out += '<span class="string">' + escapeHtml(line.slice(i,j)) + '</span>';
      i = j; continue;
    }
    if (/[0-9]/.test(c)) {
      let j = i+1;
      while (j < n && /[0-9.]/.test(line[j])) j++;
      out += '<span class="number">' + escapeHtml(line.slice(i,j)) + '</span>';
      i = j; continue;
    }
    if (/[A-Za-z_α-ωΑ-Ωℕℤℚℝℂ]/.test(c)) {
      let j = i+1;
      while (j < n && /[A-Za-z0-9_α-ωΑ-Ωℕℤℚℝℂ.'!?₀₁₂₃₄₅₆₇₈₉]/.test(line[j])) j++;
      const tok = line.slice(i, j);
      if (KEYWORDS.has(tok)) {
        out += '<span class="keyword">' + escapeHtml(tok) + '</span>';
      } else if (/^[A-Z]/.test(tok)) {
        out += '<span class="type">' + escapeHtml(tok) + '</span>';
      } else {
        out += escapeHtml(tok);
      }
      i = j; continue;
    }
    if (/[():,\\[\\]{}<>=|!&*+\\-/\\\\.;]/.test(c)) {
      out += '<span class="punct">' + escapeHtml(c) + '</span>';
      i++; continue;
    }
    out += escapeHtml(c);
    i++;
  }
  return out;
}

function tagToBucket(t) {
  if (t === 'simp') return 'simp';
  if (t.startsWith('aesop safe')) return 'safe';
  if (t.startsWith('aesop unsafe')) return 'unsafe';
  if (t === 'grind' || t.startsWith('grind')) return 'grind';
  return 'untag';
}

function declBuckets(tags) {
  if (!tags || tags.length === 0) return ['untag'];
  return tags.map(tagToBucket);
}

function lineBucket(tags) {
  const buckets = declBuckets(tags);
  if (buckets.length === 1) return buckets[0];
  return 'multi';
}

function renderLine(line, tagInfo) {
  let cls = 'code-line';
  let inlineTag = '';
  if (tagInfo) {
    const lb = lineBucket(tagInfo.tags);
    cls += ' tagged-' + lb;
    cls += ' decl-line';
    const pill = tagInfo.tags.length > 0
      ? tagInfo.tags.map(t => '<span class="pill ' + tagToBucket(t) + '">' + escapeHtml(t) + '</span>').join(' ')
      : '<span class="pill untag">untagged</span>';
    inlineTag = '<span class="inline-tag">' + pill + '</span>';
  }
  let body;
  if (/^\\s*--/.test(line)) body = '<span class="comment">' + escapeHtml(line) + '</span>';
  else if (/^\\s*\\/-/.test(line)) body = '<span class="comment">' + escapeHtml(line) + '</span>';
  else body = highlight(line);
  return { html: body, cls, inlineTag };
}

function render() {
  const e = ENTRIES[currentIdx];
  document.getElementById('hdr-section').textContent = e.section;
  document.getElementById('hdr-ndecls').textContent = e.n_decls;
  document.getElementById('hdr-ntagged').textContent = e.n_tagged + ' / ' + e.n_decls;
  document.getElementById('hdr-agent').textContent = e.agent_finished ? 'finished' : 'incomplete';

  const declByLine = {};
  e.decls.forEach(d => { declByLine[d.line] = d; });

  const lines = e.source.split('\\n');
  const codeEl = document.getElementById('code');
  let html = '';
  for (let i = 0; i < lines.length; i++) {
    const lineNo = i + 1;
    const tagInfo = declByLine[lineNo];
    const r = renderLine(lines[i], tagInfo);
    let cls = r.cls;
    let displayStyle = '';
    if (tagInfo) {
      const buckets = declBuckets(tagInfo.tags);
      const anyOn = buckets.some(b => filterState[b]);
      if (!anyOn) displayStyle = 'opacity:0.25;';
    }
    html += '<span class="' + cls + '" id="L' + lineNo + '" style="' + displayStyle + '">'
          + '<span class="ln">' + lineNo + '</span>'
          + r.html
          + r.inlineTag
          + '</span>';
  }
  codeEl.innerHTML = html;

  // Tag distribution stats
  const stats = e.tag_counts || {};
  let statsHtml = '';
  Object.keys(stats).sort().forEach(k => {
    statsHtml += '<div class="row"><span>' + escapeHtml(k) + '</span><span class="v">' + stats[k] + '</span></div>';
  });
  document.getElementById('stats').innerHTML = statsHtml || '<div class="row">(none)</div>';

  // Tagged & untagged lists
  const tagged = e.decls.filter(d => d.tags.length > 0);
  const untagged = e.decls.filter(d => d.tags.length === 0);
  const renderDecl = (d) => {
    const pills = d.tags.length > 0
      ? d.tags.map(t => '<span class="pill ' + tagToBucket(t) + '">' + escapeHtml(t) + '</span>').join(' ')
      : '<span class="pill untag">untagged</span>';
    return '<div class="decl-row" onclick="document.getElementById(\\'L' + d.line + '\\').scrollIntoView({block:\\'center\\'});">'
         + '<span class="name" title="' + escapeHtml(d.fqn) + '">' + escapeHtml(d.local) + '</span>'
         + '<span style="display:flex;gap:3px;flex-wrap:wrap;justify-content:flex-end;">' + pills + '</span>'
         + '</div>';
  };
  document.getElementById('tagged-list').innerHTML = tagged.map(renderDecl).join('') || '<div style="color:var(--muted);font-size:11px;">(none)</div>';
  document.getElementById('untagged-list').innerHTML = untagged.map(renderDecl).join('') || '<div style="color:var(--muted);font-size:11px;">(none)</div>';

  // Warnings
  const warnEl = document.getElementById('warnings');
  if (e.warnings && e.warnings.length) {
    warnEl.innerHTML = e.warnings.map(w => '<div class="warn">' + escapeHtml(w) + '</div>').join('');
  } else {
    warnEl.innerHTML = '<div style="color:var(--muted);font-size:11px;">none</div>';
  }
}

function buildSidebar() {
  const sb = document.getElementById('sidebar');
  sb.innerHTML = '';
  ENTRIES.forEach((e, idx) => {
    const a = document.createElement('div');
    a.className = 'entry-link' + (idx === currentIdx ? ' active' : '');
    a.innerHTML =
      '<span class="name">' + escapeHtml(e.section) + '</span>' +
      '<div class="meta">' +
        '<span>' + e.n_tagged + '/' + e.n_decls + ' tagged</span>' +
      '</div>';
    a.addEventListener('click', () => { currentIdx = idx; buildSidebar(); render(); });
    sb.appendChild(a);
  });
}

document.querySelectorAll('.legend .filter').forEach(f => {
  f.addEventListener('click', () => {
    const tag = f.dataset.tag;
    filterState[tag] = !filterState[tag];
    f.classList.toggle('off', !filterState[tag]);
    render();
  });
});

buildSidebar();
render();
</script>
</body>
</html>
"""

OUT.write_text(HTML.replace(PLACEHOLDER, json.dumps(entries, ensure_ascii=False)))
print(f'Wrote {OUT} ({OUT.stat().st_size:,} bytes, {len(entries)} sections)')
