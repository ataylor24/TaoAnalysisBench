"""Vendored Lean REPL harness (simple_worker + compile_lean_code).

Originally imported from
    <vendor-path-redacted>
    <vendor-path-redacted>
        alex/data_annotation_harness/toolbox/compile_lean_code.py

Vendored so omega_proof is self-contained and has no runtime dependency on
those external trees. The only remaining external dependency is the Lean
toolchain + the math_repl Lake workspace (both provisioned by
``scripts/setup.sh`` — see README "Setup").
"""

from .compile_lean_code import (
    compile_lean_code,
    compile_lean_code_structured,
    compile_lean_file,
    compile_lean_file_string,
    initialize_repl_manager,
    shutdown_repl_manager,
)

__all__ = [
    "compile_lean_code",
    "compile_lean_code_structured",
    "compile_lean_file",
    "compile_lean_file_string",
    "initialize_repl_manager",
    "shutdown_repl_manager",
]
