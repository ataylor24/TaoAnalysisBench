"""Path & runtime configuration for the agentic pipelines.

All values default to env-var lookups so the code can be invoked from
arbitrary host environments without code edits. Each variable's default
points at a sensible package-relative location; override via env when
running.

Env vars (all optional):
  LEAN_RUNTIME            — Lake project hosting the Mathlib REPL pool
  ANALYSIS_BOOK_DIRECTORY — Tao Analysis textbook source tree (with Tags/)
  ANALYSIS_BOOK_ROOT      — parent of ANALYSIS_BOOK_DIRECTORY (lakefile lives here)
  OUTPUT_DIR              — where workflow runs persist results_stream.jsonl
  CACHE_DIR               — cache for heavy intermediate artifacts
  JIXIA_EXECUTABLE        — path to jixia binary (for mathlib_translation goal-state)
  LAKE_PROJECT            — Lake project for jixia subprocess workspace
  BASELINE_INDEX_PATH     — optional FQN -> section index for relaxation
"""
import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent

# Bundled data lives at <PACKAGE_ROOT>/data/. The annotated textbook
# (with Tags/) is the default source the workflows operate on.
LEAN_RUNTIME = os.environ.get(
    "LEAN_RUNTIME", str(PACKAGE_ROOT / "lean_runtime")
)
ANALYSIS_BOOK_DIRECTORY = os.environ.get(
    "ANALYSIS_BOOK_DIRECTORY",
    str(PACKAGE_ROOT / "data" / "textbook_annotated" / "Analysis"),
)
ANALYSIS_BOOK_ROOT = os.environ.get(
    "ANALYSIS_BOOK_ROOT",
    str(PACKAGE_ROOT / "data" / "textbook_annotated"),
)
OUTPUT_DIR = os.environ.get(
    "OUTPUT_DIR", str(PACKAGE_ROOT / "output")
)
os.makedirs(OUTPUT_DIR, exist_ok=True)

CACHE_DIR = os.environ.get(
    "CACHE_DIR", str(PACKAGE_ROOT / ".cache")
)
os.makedirs(CACHE_DIR, exist_ok=True)

JIXIA_EXECUTABLE = os.environ.get("JIXIA_EXECUTABLE", "")
LAKE_PROJECT = os.environ.get("LAKE_PROJECT", LEAN_RUNTIME)

BASELINE_INDEX_PATH = os.environ.get(
    "BASELINE_INDEX_PATH",
    str(PACKAGE_ROOT / "data" / "baseline_index.json"),
)
