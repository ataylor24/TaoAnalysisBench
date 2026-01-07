#!/usr/bin/env python3
"""
compile_jsonl_lean.py

Read a JSONL of Lean snippets and compile each one with the `lean` binary.
Assumes each JSONL line is either:
  - a dict with a "content" field containing Lean code, or
  - a dict with a "code" field containing Lean code, or
  - a raw JSON string containing Lean code.

By default this uses `lean --make` on a temp Main.lean per snippet.
You can force specific imports to appear at the VERY TOP of the file with --force-imports,
e.g., --force-imports "Init,Mathlib.Tactic".
"""

import tempfile
from pathlib import Path
import subprocess
from typing import List, Any
import time
import math
from globals import LAKE_PROJECT
import json

def compile_with_lean(lean_exe: str, src_path: Path, timeout: int) -> subprocess.CompletedProcess:
    # Prefer `lean --make` so transitive imports (on LEAN_PATH) get built/checked.
    # Run from the snippet directory to improve relative import resolution.
    # Use Lake environment so Mathlib and other deps resolve.
    cmd_make = ["lake", "env", lean_exe, "--make", str(src_path)]
    cmd_plain = ["lake", "env", lean_exe, str(src_path)]
    run_cwd = str(LAKE_PROJECT)
    try:
        proc = subprocess.run(
            cmd_make,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=run_cwd,
            timeout=timeout if timeout > 0 else None,
        )
        if proc.returncode == 0:
            return proc
        # Fallback: try plain `lean` (no --make) which can be more permissive for standalone files
        proc2 = subprocess.run(
            cmd_plain,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=run_cwd,
            timeout=timeout if timeout > 0 else None,
        )
        return proc2
    except subprocess.TimeoutExpired as e:
        # Synthesize a CompletedProcess-like object
        cp = subprocess.CompletedProcess(cmd_make, returncode=124, stdout=e.stdout or "", stderr=e.stderr or "timeout")
        return cp

def compile_lean_code(code: str) -> str:
    time_prefix = math.floor(time.time())
    base_tmp = tempfile.mkdtemp(prefix=f"lean_compile_{time_prefix}_", dir=str(LAKE_PROJECT))
    base_tmp_path = Path(base_tmp)
    
    snip_dir = base_tmp_path / f"{time_prefix}_snippet"
    snip_dir.mkdir(parents=True, exist_ok=True)
    main_lean = snip_dir / "Main.lean"

    main_lean.write_text(code, encoding="utf-8")

    proc = compile_with_lean(lean_exe = "lean", src_path = main_lean, timeout = 120)

    if proc.returncode == 0:
        return "The code compiled successfully."
    else:
        result = {
            "success": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
        return "The code did not compile correctly. Please look through the error messages carefully and try again.\nLEAN_COMPILE_RESULT\n" + json.dumps(result) + "\nEND_LEAN_COMPILE_RESULT\n"

