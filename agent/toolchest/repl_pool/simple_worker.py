#!/usr/bin/env python3
"""
Lean REPL worker optimized for RL pipelines.
Sequentially verifies proofs, halting at the first error, and tracks outer goal contexts.
"""
import subprocess
import os
import json
import time
import signal
import queue
import threading
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple
import re
from dataclasses import dataclass

# Import the LeanCodeSplitter
# try:
#     from utils import LeanCodeSplitter, Tactic, TacticConverter
# except ImportError:
#     import sys
#     _dir = Path(__file__).parent
#     sys.path.insert(0, str(_dir))
#     from utils import LeanCodeSplitter, Tactic, TacticConverter
#     sys.path.remove(str(_dir))

@dataclass
class Tactic:
    """Represents a single tactic that can be sent to REPL"""
    content: str
    indent_level: int
    line_number: int
    is_nested_proof_header: bool = False
    
    def __repr__(self):
        nested_marker = " [NESTED]" if self.is_nested_proof_header else ""
        return f"Tactic(indent={self.indent_level}{nested_marker}): {self.content[:50]}"


class TacticConverter:
    """
    Helper to convert tactics for REPL execution.
    
    The converter prepares tactics for sending to the Lean REPL by:
    1. Stripping leading/trailing whitespace (REPL doesn't need indentation)
    2. For nested proof headers (e.g., 'have h := by'), appending ' sorry' to create
       a placeholder that allows entering the nested proof context
    """
    
    @staticmethod
    def prepare_for_repl(tactic: Tactic) -> str:
        """
        Prepare a tactic for sending to REPL.
        
        Preserves all whitespace and indentation. For nested proof headers,
        appends ' sorry' to create a placeholder that allows entering the nested proof context.
        All original spacing is preserved.
        """
        
        #MAYBEFIX
        # content = tactic.content
        
        # if tactic.is_nested_proof_header:
        #     # For nested proof headers, append ' sorry' preserving all whitespace
        #     # Check if it ends with 'by' (with possible trailing whitespace)
        #     # We preserve all original whitespace and just append ' sorry'
        #     if content.rstrip().endswith('by'):
        #         # Preserve trailing whitespace if any, then add ' sorry'
        #         return content + ' sorry'
        #     else:
        #         return content + ' sorry'
        # else:
        #     return content
        
        cleaned = tactic.content.strip()
    
        # FIX: Remove ":= by" or ":=" from the end of have/let statements
        # This allows the REPL to accept it as an "Open Goal"
        if cleaned.startswith("have ") or cleaned.startswith("let ") or cleaned.startswith("suffices "):
            if cleaned.endswith(":= by"):
                return cleaned[:-5].strip() # Remove ":= by"
            if cleaned.endswith(":="):
                return cleaned[:-2].strip() # Remove ":="
                
        return cleaned


class LeanCodeSplitter:
    """Lean 4 code splitter that produces individual tactics for REPL execution."""
    
    def split(self, full_code: str) -> Tuple[str, str, List[Tactic]]:
        """
        Split Lean code into header, theorem statement, and tactics.
        
        Preserves all whitespace and indentation in the returned strings.
        """
        match = re.search(
            r'(.*?)(\b(?:theorem|lemma|example)\b.*)',
            full_code,
            re.DOTALL
        )
        
        if not match:
            return full_code, "", []
        
        header, body = match.groups()
        
        import_match = re.match(r'([\s\S]*\bimport\b[^\n]*)(.*)', header, re.DOTALL)

        if import_match:
            imports, header_remainder = import_match.groups()
        else:
            imports = ""
            header_remainder = header
        
        
        stmt_match = re.search(r'(.*?:=\s*by)(.*)', body, re.DOTALL)
        
        if not stmt_match:
            return header, body, []
        
        theorem_stmt, proof_block = stmt_match.groups()
        tactics = self._extract_tactics(proof_block)
        
        return imports, header_remainder, theorem_stmt, tactics
    
    def _extract_tactics(self, proof_block: str) -> List[Tactic]:
        """
        Extract individual tactics from a proof block.
        
        Preserves the original indentation structure of the code.
        Each tactic's content maintains the exact indentation as it appears
        in the original source, including relative indentation for multi-line tactics.
        """
        lines = proof_block.split('\n')
        tactics = []
        
        i = 0
        line_num = 0
        
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            if not stripped or stripped.startswith('--'):
                i += 1
                line_num += 1
                continue
            
            indent = self._get_indent(line)
            is_nested_header = self._is_nested_proof_header(stripped)
            
            tactic_lines, next_i = self._collect_single_tactic(lines, i, indent)
            # Join lines preserving original indentation
            tactic_content = '\n'.join(tactic_lines)
            
            tactic = Tactic(
                content=tactic_content,
                indent_level=indent,
                line_number=line_num,
                is_nested_proof_header=is_nested_header
            )
            
            tactics.append(tactic)
            i = next_i
            line_num += len(tactic_lines)
        
        return tactics
    
    def _is_nested_proof_header(self, line: str) -> bool:
        """Check if a line is a nested proof header."""
        patterns = [
            r'\bhave\b.*:=\s*by\s*$',
            r'\bshow\b.*\s+by\s*$',
            r'\bsuffices\b.*\s+by\s*$',
            r'\blet\b.*:=\s*by\s*$',
        ]
        
        for pattern in patterns:
            if re.search(pattern, line):
                return True
        return False
    
    def _collect_single_tactic(self, lines: List[str], start_idx: int, base_indent: int) -> Tuple[List[str], int]:
        """
        Collect a single tactic (may span multiple lines).
        
        Preserves the original indentation of all lines in the tactic.
        Lines are collected as-is without any modification to whitespace.
        
        Ensures blocks of "with" or "calc" are not broken up
        """
        start_line = lines[start_idx]
        tactic_lines = [start_line]
        
        if self._is_nested_proof_header(start_line.strip()):
            return tactic_lines, start_idx + 1
        
        i = start_idx + 1
        paren_depth = self._count_unclosed_parens(lines[start_idx])
        
        # Detect if we are starting a layout-sensitive block 
        # (e.g., 'induction ... with', 'match ... with', or ending in '=>')
        in_layout_block = start_line.strip().endswith(' with') or start_line.strip().endswith('=>')
        current_case_body_indent = None
        
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            if not stripped or stripped.startswith('--'):
                if in_layout_block or paren_depth > 0:
                    # Inside a block, preserve whitespace and comments
                    tactic_lines.append(line)
                    i += 1
                    continue
                else:
                    # Outside a block, skip them
                    i += 1
                    continue
            
            current_indent = len(line) - len(line.lstrip())
            is_continuation = False
            
            if in_layout_block:
                if stripped.startswith('|'):
                    # We hit a new branch case (e.g., "| succ =>")
                    # Reset the body indent tracker for the new branch
                    current_case_body_indent = None
                    is_continuation = True
                else:
                    if current_case_body_indent is None:
                        # This is the first line AFTER the '| ... =>' or 'with'.
                        # It establishes the baseline indentation for this specific case body.
                        current_case_body_indent = current_indent
                        is_continuation = True
                    else:
                        # Continue consuming lines as long as we stay at or deeper 
                        # than the established case body indentation.
                        if current_indent >= current_case_body_indent:
                            is_continuation = True
                        else:
                            # The indentation outdented past the case body.
                            # This means the entire induction/match block is finished.
                            is_continuation = False
            
            if re.match(r'^[<>|.,;)\]]', stripped):
                is_continuation = True
            elif tactic_lines and self._ends_with_combinator(tactic_lines[-1]):
                is_continuation = True
            elif paren_depth > 0:
                is_continuation = True
            elif tactic_lines and self._ends_incomplete(tactic_lines[-1]):
                is_continuation = True
            
            if is_continuation:
                tactic_lines.append(line)
                paren_depth += self._count_unclosed_parens(line)
                
                # If an inner line triggers a NEW block (e.g., a nested match or lambda),
                # we reset the layout tracker to follow the inner block's rules.
                if stripped.endswith('=>') or stripped.endswith(' with'):
                    in_layout_block = True
                    current_case_body_indent = None
                
                i += 1
            else:
                break
        
        return tactic_lines, i
    
    def _get_indent(self, line: str) -> int:
        """Get indentation level."""
        return len(line) - len(line.lstrip(' '))
    
    def _count_unclosed_parens(self, line: str) -> int:
        """Count unclosed parentheses."""
        cleaned = re.sub(r'"[^"]*"', '', line)
        cleaned = re.sub(r'--.*$', '', cleaned)
        
        open_count = cleaned.count('(') + cleaned.count('[') + cleaned.count('{')
        close_count = cleaned.count(')') + cleaned.count(']') + cleaned.count('}')
        
        return open_count - close_count
    
    def _ends_with_combinator(self, line: str) -> bool:
        """Check if line ends with a combinator."""
        stripped = line.strip()
        stripped = re.sub(r'--.*$', '', stripped).strip()
        
        combinators = ['<;>', '|>', '<|>', ';', '$', '>>', '<<']
        return any(stripped.endswith(comb) for comb in combinators)
    
    def _ends_incomplete(self, line: str) -> bool:
        """Check if line ends incompletely."""
        stripped = line.strip()
        stripped = re.sub(r'--.*$', '', stripped).strip()
        
        incomplete_endings = ['+', '-', '*', '/', '∘', '∧', '∨', '→', '↔', ',', '=', '≠', '<', '>', '≤', '≥']
        return any(stripped.endswith(ending) for ending in incomplete_endings)

#Annoying imports from utils.py above^

class LeanREPLSimpleWorker:
    """
    Streamlined REPL worker for RL verification.
    Executes tactics linearly, tracks goal state contexts via indentation, 
    and halts at the first error.
    """
    
    def __init__(self, lean_dir: str, worker_id: int = 0, verbose: bool = False):
        self.lean_dir = lean_dir
        self.worker_id = worker_id
        self.proc = None
        self.base_env = None
        self.verbose = verbose
        self._lifecycle_lock = threading.Lock()
        
        self.splitter = LeanCodeSplitter()
        self.converter = TacticConverter()
        
    def start(self, timeout: float = 180.0):
        """Start the REPL process and load imports (BLOCKING)."""
        with self._lifecycle_lock:
            self._kill_unlocked()
            
            # Drop stdbuf on macOS — Homebrew's stdbuf is x86_64-only and
            # crashes on arm64 Macs. The REPL is line-oriented and bufsize=1
            # below handles buffering.
            if sys.platform == "darwin":
                cmd = ["lake", "exe", "repl"]
            else:
                cmd = ["stdbuf", "-i0", "-o0", "-e0", "lake", "exe", "repl"]
            if self.verbose:
                print(f"🟢 Starting REPL worker {self.worker_id}")
            
            self.proc = subprocess.Popen(
                cmd,
                cwd=self.lean_dir,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                start_new_session=True
            )
            time.sleep(1)

        # WARMUP REPL
        header = (
            "import Mathlib\n"
            "import Aesop\n\n"
            "set_option maxHeartbeats 2000000\n\n"
            "open BigOperators Real Nat Topology Rat\n"
        )
        
        try:
            res, _ = self._send_command({"cmd": header}, timeout=timeout)
            
            if "env" not in res:
                raise RuntimeError(f"Worker {self.worker_id}: Failed to load imports")
            
            self.base_env = res["env"]
            if self.verbose:
                print(f"✅ Worker {self.worker_id} ready (base_env={self.base_env})")
            
        except Exception as e:
            print(f"🟥 Worker {self.worker_id} start error: {e}")
            self.kill()
            raise
    
    def check_proof(self, code: str, timeout: float = 30.0) -> Dict[str, Any]:
        """
        Verify a full proof string. 
        Returns the final goal state on success, or the error and previous goal state on failure.
        """
        imports, header, theorem_stmt, tactics = self.splitter.split(code)
        
        # Reset to base environment (Env 1) for every new proof check
        curr_env = self.base_env
        
        # 1. Execute snippet-specific header if present
        if header.strip():
            res, _ = self._send_command({"cmd": header, "env": curr_env}, timeout=timeout)
            if "env" in res:
                curr_env = res["env"]
        
        # 2. Initialize proof
        init_cmd = f"{theorem_stmt} sorry"
        try:
            res, _ = self._send_command({"cmd": init_cmd, "env": curr_env}, timeout=timeout)
            
            error_msg = self._extract_error(res)
            if error_msg:
                return self._build_error_payload(error_msg, "Initialization", [], [])
            
            sorries = res.get("sorries", [])
            if not sorries:
                return self._build_error_payload("No proof state returned on init.", "Initialization", [], [])
            
            current_proof_state = sorries[0].get("proofState")
            if "env" in res:
                curr_env = res["env"]
                
        except Exception as e:
            return self._build_error_payload(str(e), "Initialization", [], [])

        # 3. Track execution state
        # Stack tracks dictionaries of {"indent": int, "goals": List[str]} to maintain outer contexts
        context_stack = [] 
        prev_goals = res.get("goals", [])
        
        # 4. Execute tactics linearly
        for tactic in tactics:
            # Clean up outer contexts if we dedent (return to an outer scope)
            while context_stack and context_stack[-1]["indent"] >= tactic.indent_level:
                context_stack.pop()
            
            repl_tactic = self.converter.prepare_for_repl(tactic)
            cmd_dict = {
                "tactic": repl_tactic,
                "proofState": current_proof_state,
                "env": curr_env
            }
            
            try:
                res, _ = self._send_command(cmd_dict, timeout=timeout)
                
                # Check for errors
                error_msg = self._extract_error(res)
                if error_msg:
                    outer_contexts = [ctx["goals"] for ctx in context_stack]
                    return self._build_error_payload(error_msg, tactic.content, prev_goals, outer_contexts)
                
                # Update states on success
                if "proofState" in res:
                    current_proof_state = res["proofState"]
                
                current_goals = res.get("goals", [])
                prev_goals = current_goals
                
                # Push the current state to the context stack for future tactics
                context_stack.append({"indent": tactic.indent_level, "goals": current_goals})
                
            except Exception as e:
                outer_contexts = [ctx["goals"] for ctx in context_stack]
                return self._build_error_payload(str(e), tactic.content, prev_goals, outer_contexts)
            
        # 5. Successfully executed all tactics
        outer_contexts = [ctx["goals"] for ctx in context_stack[:-1]] if context_stack else []
        return {
            "success": True,
            "error": None,
            "failed_tactic": None,
            "final_goals": prev_goals,
            # "outer_contexts": outer_contexts
        }

    def _extract_error(self, response: Dict) -> str:
        """Helper to safely extract real errors from the REPL response."""
        if "error" in response:
            return response["error"]
        
        single_message = response.get("message", "")
        if "Lean error" in single_message:
            return single_message
            
        messages = response.get("messages", [])
        msg_errors = [m for m in messages if m.get("severity") == "error"]
        if msg_errors:
            error_data = msg_errors[0].get("data", "")
            # "unsolved goals" is standard when goals remain, not a syntax/compilation error
            if not error_data.startswith("unsolved goals"):
                return error_data
        
        return None

    def _build_error_payload(self, error: str, tactic: str, prev_goals: List[str], outer_contexts: List[List[str]]) -> Dict:
        """Helper to format the failure response."""
        return {
            "success": False,
            "error": error,
            "failed_tactic": tactic,
            "previous_goals": prev_goals,
            # "outer_contexts": outer_contexts
        }

    def _send_command(self, cmd_dict: Dict, timeout: float = 30.0) -> Tuple[Dict, str]:
        """Send command to REPL and read response with timeout."""
        json_line = json.dumps(cmd_dict) + "\n\n"
        
        try:
            self.proc.stdin.write(json_line)
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError):
            raise EOFError("REPL closed connection unexpectedly")

        result_queue = queue.Queue()
        exception_queue = queue.Queue()
        
        def read_response():
            try:
                lines = []
                json_started = False
                while True:
                    line = self.proc.stdout.readline()
                    if not line:
                        exception_queue.put(EOFError("REPL closed connection"))
                        return

                    if not line.strip():
                        if not lines:
                            continue
                        else:
                            break

                    stripped_line = line.strip()
                    if not json_started:
                        if stripped_line.startswith("{") or stripped_line.startswith("["):
                            json_started = True
                            lines.append(line)
                    else:
                        lines.append(line)

                full_output = "".join(lines)
                try:
                    result = json.loads(full_output)
                except json.JSONDecodeError:
                    # Fallback line-by-line parsing
                    last_obj = None
                    for ln in full_output.splitlines():
                        ln = ln.strip()
                        if not ln: continue
                        try:
                            last_obj = json.loads(ln)
                        except json.JSONDecodeError:
                            continue
                    if last_obj is not None:
                        result = last_obj
                    else:
                        exception_queue.put(json.JSONDecodeError("parse failed", full_output, 0))
                        return
                
                result_queue.put((result, full_output))
            except Exception as e:
                exception_queue.put(e)
        
        reader_thread = threading.Thread(target=read_response, daemon=False)
        reader_thread.start()
        
        try:
            result, raw_output = result_queue.get(timeout=timeout)
            return result, raw_output
        except queue.Empty:
            raise TimeoutError("REPL timed out")
        finally:
            if not exception_queue.empty():
                raise exception_queue.get()

    def kill(self):
        """Terminate the REPL process."""
        with self._lifecycle_lock:
            return self._kill_unlocked()
    
    def _kill_unlocked(self):
        """Internal kill implementation."""
        if self.proc is None:
            return None
        
        pid = self.proc.pid
        pgid = None
        
        try:
            pgid = os.getpgid(pid)
        except (OSError, ProcessLookupError):
            pass
            
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
            
            if pgid is not None:
                os.killpg(pgid, signal.SIGTERM)
            else:
                self.proc.terminate()
            
            self.proc.wait(timeout=2.0)
        except Exception:
            try:
                if pgid is not None:
                    os.killpg(pgid, signal.SIGKILL)
                else:
                    self.proc.kill()
            except Exception:
                pass
                
        self.proc = None
        return pid

# ============= Quick Test Execution =============
if __name__ == "__main__":
    # os.environ['LEAN_DIR'] = "/Users/vigyansahai/Code/omega_proof/v4.28.0"
    lean_dir = os.environ.get("LEAN_DIR") or os.environ.get("LAKE_PROJECT")
    if not lean_dir:
        raise SystemExit(
            "Set LEAN_DIR (or LAKE_PROJECT) to the math_repl workspace path, "
            "e.g. `export LAKE_PROJECT=/path/to/kimina-lean-server/workspace/math_repl`."
        )
    worker = LeanREPLSimpleWorker(lean_dir=lean_dir, verbose=True)
    try:
        worker.start()
#         test_code = """
# theorem test_addition (a b : Nat) : a + b = b + a := by
#   have h1 : a + 0 = a := by rfl
#   sorry
# """
        # test_code = "import Mathlib\\n\\ntheorem number_theory_46533_v0005 (x y : ℤ) (hx : 10 ≤ x ∧ x ≤ 99) (hy : 10 ≤ y ∧ y ≤ 99) :\\n    109 ≤ x * (100 - y) + y := by\\n  cases' hx with hx1 hx2\\n  cases' hy with hy1 hy2\\n  have : 109 ≤ x * (100 - y) + y := by\\n    have hx_min : x ≥ 10 := hx1\\n    have hx_max : x ≤ 99 := hx2\\n    have hy_min : y ≥ 10 := hy1\\n    have hy_max : y ≤ 99 := hy2\\n    linarith\\n  exact this"
        test_code = '''import Mathlib

theorem number_theory_46533_v0005 (x y : ℤ) (hx : 10 ≤ x ∧ x ≤ 99) (hy : 10 ≤ y ∧ y ≤ 99) :
    109 ≤ x * (100 - y) + y := by
  cases' hx with hx1 hx2
  cases' hy with hy1 hy2
  have : 109 ≤ x * (100 - y) + y := by
    have hx_min : x ≥ 10 := hx1
    have hx_max : x ≤ 99 := hx2
    have hy_min : y ≥ 10 := hy1
    have hy_max : y ≤ 99 := hy2
    linarith
  exact this'''
        
        result = worker.check_proof(test_code)
        print(json.dumps(result, indent=2))
    finally:
        worker.kill()