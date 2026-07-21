#!/usr/bin/env python3
"""
Lean REPL-based compilation tool optimized for concurrent harness execution.
Uses a pool of persistent REPL workers instead of spawning fresh processes per call.

Vendored into omega_proof from
    Central_Math_Repo/alex/data_annotation_harness/toolbox/compile_lean_code.py
The original file injected sys.path to import ``simple_worker`` and optionally
imported ``LAKE_PROJECT`` from a hand-maintained ``globals.py``. Both are
replaced here with a package-relative import and an explicit ``LAKE_PROJECT``
environment variable (callers pass the path in through ``initialize_repl_manager``
anyway, so this fallback is only for the ``__main__`` demo block).
"""

import json
import os
import concurrent.futures
import queue
import threading
import time
from typing import Optional

from .simple_worker import LeanREPLSimpleWorker

LAKE_PROJECT = os.getenv("LAKE_PROJECT", "")

MAX_USES_PER_WORKER = 250  # After this many uses, we will restart the REPL to prevent memory leaks

class LeanREPLManager:
    """
    Thread-safe pool manager for REPL workers.
    Maintains a queue of LeanREPLSimpleWorker instances for concurrent access.
    """
    
    def __init__(self, lean_dir: str, max_workers: int, verbose: bool = False, init_timeout: float = 500.0):
        self.lean_dir = lean_dir
        self.max_workers = max_workers
        self.verbose = verbose
        self.init_timeout = init_timeout
        self.available = queue.Queue()
        self._lock = threading.Lock()
        self._initialized = False
        self._active_workers = set()
        
        # Track usage to prevent memory leaks
        self.worker_usage = {}
    
    def boot_single_worker(self, worker_id: int) -> LeanREPLSimpleWorker:
        """Boot a single REPL worker instance."""
        if self.verbose:
            print(f"🟢 Booting REPL worker {worker_id}...")
        repl = LeanREPLSimpleWorker(
            lean_dir=self.lean_dir,
            worker_id=worker_id,
            verbose=self.verbose
        )
        repl.start(timeout=self.init_timeout)
        return repl
    
    def start(self):
        """Initialize all REPL worker instances CONCURRENTLY."""
        with self._lock:
            if self._initialized:
                raise RuntimeError("REPL manager already initialized")
            
            if self.verbose:
                print(f"🟢 Initializing REPL manager with {self.max_workers} workers...")
            
            #Multi-threaded boot to speed up initialization
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {executor.submit(self.boot_single_worker, i): i for i in range(self.max_workers)}
                
                for future in concurrent.futures.as_completed(futures):
                    worker_id = futures[future]
                    try:
                        repl = future.result()
                        self._active_workers.add(repl)
                        self.worker_usage[repl] = 0
                        self.available.put(repl)
                    except Exception as e:
                        print(f"🟥 Failed to start REPL worker {worker_id}: {e}")
                        self.shutdown() # Cascade shutdown if we fail to boot
                        raise
            
            
            self._initialized = True
            if self.verbose:
                print(f"✅ REPL manager ready with {len(self._active_workers)} workers")
    
    def shutdown(self):
        """Terminate all REPL workers (blocking call)."""
        with self._lock:
            if self.verbose:
                print(f"🔴 Shutting down REPL manager...")
            
            for repl in list(self._active_workers):
                try:
                    repl.kill()
                except Exception as e:
                    print(f"⚠️  Error killing REPL worker {repl.worker_id}: {e}")
            
            self._active_workers.clear()
            self.worker_usage.clear()
            
            # Drain the queue
            while not self.available.empty():
                try:
                    self.available.get_nowait()
                except queue.Empty:
                    break
            
            self._initialized = False
    
    def get_repl(self, timeout: float = 60.0) -> LeanREPLSimpleWorker:
        """Borrow a REPL instance from the pool (blocks if none available)."""
        if not self._initialized:
            raise RuntimeError("REPL manager not initialized")
        try:
            return self.available.get(timeout=timeout)
        except queue.Empty:
            raise TimeoutError(f"No REPL available after {timeout}s (pool exhausted)")
    
    def return_repl(self, repl: LeanREPLSimpleWorker):
        """Return a REPL instance to the pool. If it has exceeded max uses or is dead, restart it."""
        
        is_dead = repl.proc is None or repl.proc.poll() is not None
        
        usage_count = self.worker_usage.get(repl, 0) + 1
        needs_recycle = usage_count >= MAX_USES_PER_WORKER
        
        if is_dead or needs_recycle:
            if self.verbose:
                reason = "dead" if is_dead else "max uses exceeded"
                if self.verbose:
                    print(f"♻️  Recycling REPL worker {repl.worker_id} ({reason})...")
            try:
                repl.kill()
            except Exception as e:
                print(f"⚠️  Error killing REPL worker {repl.worker_id}: {e}")
            try:
                new_repl = self.boot_single_worker(repl.worker_id)
                with self._lock:
                    self._active_workers.discard(repl)
                    self._active_workers.add(new_repl)
                    self.worker_usage.pop(repl, None)
                    self.worker_usage[new_repl] = 0
                self.available.put(new_repl)
            except Exception as e:
                print(f"🟥 Failed to respawn worker {repl.worker_id}: {e}")
        else:
            self.worker_usage[repl] = usage_count
            self.available.put(repl)
        
        


# Global manager instance and lock
_repl_manager: Optional[LeanREPLManager] = None
_manager_lock = threading.Lock()


def initialize_repl_manager(lean_dir: str, max_workers: int, verbose: bool = False, init_timeout: float = 500.0):
    """
    Initialize the global REPL manager. Call once at harness startup.
    
    Args:
        lean_dir: Path to Lean Lake project directory
        max_workers: Number of REPL instances to create (typically == max_concurrent LLMs)
        verbose: Enable debug logging
        init_timeout: Timeout for initializing each REPL instance
    """
    global _repl_manager
    with _manager_lock:
        if _repl_manager is not None:
            raise RuntimeError("REPL manager already initialized")
        
        if LeanREPLSimpleWorker is None:
            raise ImportError("simple_worker.LeanREPLSimpleWorker not available")
        
        _repl_manager = LeanREPLManager(lean_dir, max_workers, verbose=verbose, init_timeout=init_timeout)
        _repl_manager.start()


def shutdown_repl_manager():
    """Shutdown the global REPL manager. Call in finally block at harness shutdown."""
    global _repl_manager
    with _manager_lock:
        if _repl_manager is not None:
            _repl_manager.shutdown()
            _repl_manager = None



def compile_lean_code(code: str) -> str:
    """
    Compile Lean code using a persistent REPL worker (requires manager to be initialized).
    
    Returns:
        - Success: "The code compiled successfully."
        - Failure: JSON error report between LEAN_COMPILE_RESULT markers
    """
    global _repl_manager
    
    if _repl_manager is None:
        raise RuntimeError(
            "REPL manager not initialized. Call initialize_repl_manager() first. "
        )
    
    repl = None
    try:
        # Borrow a REPL from the pool
        repl = _repl_manager.get_repl(timeout=60.0)
        
        # Check the proof using the REPL
        result = repl.check_proof(code)
        
        # Format response for agent
        if result.get("success"):
            return "The code compiled successfully."
        else:
            error = result.get("error", "Unknown error")
            failed_tactic = result.get("failed_tactic", "unknown")
            
            # Convert REPL result to subprocess-like format for consistency
            repl_response = {
                "success": False,
                "returncode": 1,
                "error": error,
                "failed_tactic": failed_tactic,
                "previous_goals": result.get("previous_goals", []),
                # "outer_contexts": result.get("outer_contexts", []),
            }
            
            return (
                "The code did not compile correctly. Please look through the error messages carefully and try again.\n"
                "LEAN_COMPILE_RESULT\n"
                + json.dumps(repl_response)
                + "\nEND_LEAN_COMPILE_RESULT\n"
            )
    except Exception as e:
        repl_response = {
            "success": False,
            "returncode": 1,
            "error": f"REPL communication error: {str(e)}",
            "failed_tactic": "unknown",
            "previous_goals": []
        }
        return (
            "The code caused a catastrophic REPL failure or timeout.\n"
            "LEAN_COMPILE_RESULT\n"
            + json.dumps(repl_response)
            + "\nEND_LEAN_COMPILE_RESULT\n"
        )
    finally:
        # Always return the REPL to the pool
        if repl is not None:
            _repl_manager.return_repl(repl)


def compile_lean_file(code: str, timeout: float = 120.0) -> dict:
    """Compile a whole Lean file (imports + defs + theorems) at once.

    Unlike ``check_proof`` (which splits into tactics and runs them serially),
    this sends the entire body as a single REPL command on top of the worker's
    pre-loaded base environment with `import Mathlib`. Top-level `import` lines
    in the input are stripped — they would be illegal at non-zero env, and the
    base env already has the Mathlib import we need.

    Returns: {"success": bool, "error": str|None, "first_error_line": int|None,
              "messages": list}.
    """
    import re

    global _repl_manager
    if _repl_manager is None:
        raise RuntimeError("REPL manager not initialized.")

    stripped = "\n".join(
        ln for ln in code.splitlines() if not re.match(r"\s*import\s+\S", ln)
    )
    repl = None
    try:
        repl = _repl_manager.get_repl(timeout=60.0)
        try:
            res, _ = repl._send_command(
                {"cmd": stripped, "env": repl.base_env}, timeout=timeout
            )
        except Exception as e:
            return {
                "success": False,
                "error": f"{type(e).__name__}: {e}",
                "first_error_line": None,
                "messages": [],
            }

        messages = res.get("messages", []) or []
        if "error" in res:
            return {
                "success": False,
                "error": res["error"],
                "first_error_line": None,
                "messages": messages,
            }
        errors = [m for m in messages if m.get("severity") == "error"]
        if errors:
            first = errors[0]
            return {
                "success": False,
                "error": first.get("data", "<no data>"),
                "first_error_line": (first.get("pos") or {}).get("line"),
                "messages": messages,
            }
        return {
            "success": True,
            "error": None,
            "first_error_line": None,
            "messages": messages,
        }
    finally:
        if repl is not None:
            _repl_manager.return_repl(repl)


def compile_lean_file_string(code: str, timeout: float = 120.0) -> str:
    """Whole-file compile, formatted for an LLM tool result.

    Returns either "The code compiled successfully." or a
    LEAN_COMPILE_RESULT … END_LEAN_COMPILE_RESULT JSON envelope so existing
    prompts/regex still work.
    """
    result = compile_lean_file(code, timeout=timeout)
    if result.get("success"):
        return "The code compiled successfully."
    payload = {
        "success": False,
        "returncode": 1,
        "error": result.get("error", "Unknown error"),
        "first_error_line": result.get("first_error_line"),
    }
    return (
        "The code did not compile correctly. Please look through the error messages carefully and try again.\n"
        "LEAN_COMPILE_RESULT\n"
        + json.dumps(payload)
        + "\nEND_LEAN_COMPILE_RESULT\n"
    )


def compile_lean_code_structured(code: str) -> dict:
    """Run check_proof and return the raw REPL dict.

    Unlike compile_lean_code (which stringifies), this preserves final_goals so
    callers can distinguish "every tactic type-checked AND all goals closed"
    from "tactics type-checked but goals remain" (a no-op like `norm_cast` on a
    propositional goal).

    Shape: {"success": bool, "error": str|None, "failed_tactic": str|None,
            "final_goals": list[str], "previous_goals": list[str]}
    """
    global _repl_manager
    if _repl_manager is None:
        raise RuntimeError("REPL manager not initialized. Call initialize_repl_manager() first.")
    repl = None
    try:
        repl = _repl_manager.get_repl(timeout=60.0)
        return repl.check_proof(code)
    except Exception as e:
        return {
            "success": False,
            "error": f"REPL communication error: {str(e)}",
            "failed_tactic": "unknown",
            "previous_goals": [],
            "final_goals": [],
        }
    finally:
        if repl is not None:
            _repl_manager.return_repl(repl)


if __name__ == "__main__":
    lean_dir = os.environ.get("LAKE_PROJECT") or LAKE_PROJECT
    if not lean_dir:
        raise SystemExit(
            "Set LAKE_PROJECT to the math_repl workspace path before running "
            "this module's __main__ demo (e.g. "
            "`export LAKE_PROJECT=/path/to/kimina-lean-server/workspace/math_repl`)."
        )
    start_time = time.time()
    initialize_repl_manager(lean_dir=lean_dir, max_workers=4, verbose=True)
    init_time = time.time()
    print(f"REPL manager initialized in {init_time - start_time:.2f} seconds")
    try:
        test_code = """import Mathlib

theorem add_comm2 (a b : Nat) : a + b = b + a := by
  rw [Nat.add_comm]"""
        print(compile_lean_code(test_code))
        end_time = time.time()
        print(f"Execution time: {end_time - init_time:.2f} seconds")
    finally:
        shutdown_repl_manager()