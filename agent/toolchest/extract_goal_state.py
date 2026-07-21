"""
Extract the final Lean goal state from a snippet using Jixia.

Writes the snippet to a temp file, runs Jixia with -l (lines mode),
and parses the resulting JSON to extract the last goal state.
"""

import subprocess
import json
import tempfile
import os
from pathlib import Path
from globals import LAKE_PROJECT, JIXIA_EXECUTABLE


def extract_goal_state(lean_code: str) -> str:
    """Run Jixia on lean_code and return the final goal state string.

    Returns a string like:
        x : ℝ
        hx : x > 0
        ⊢ x ≥ 0

    On failure, returns an error message string.
    """
    with tempfile.TemporaryDirectory(dir=str(LAKE_PROJECT)) as tmpdir:
        lean_file = Path(tmpdir) / "GoalState.lean"
        output_file = Path(tmpdir) / "GoalState.lines.json"

        lean_file.write_text(lean_code, encoding="utf-8")

        cmd = [
            "lake", "env",
            JIXIA_EXECUTABLE,
            "-i",
            "-l", str(output_file),
            str(lean_file),
        ]

        result = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            check=False,
            cwd=str(LAKE_PROJECT),
            timeout=120,
        )

        if result.returncode != 0:
            return f"Jixia error (exit {result.returncode}): {result.stderr[:500]}"

        if not output_file.exists():
            return "Jixia produced no output file."

        try:
            with open(output_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            return f"Failed to parse Jixia output: {e}"

        # Walk through the states and collect them
        all_states = []
        for entry in data:
            states = entry.get("state", [])
            for st in states:
                parts = []
                ctx = st.get("context", [])
                goal = st.get("type", "")

                for hyp in ctx:
                    name_list = hyp.get("name", [])
                    name = str(name_list[-1]) if name_list else "_"
                    ty = hyp.get("type", "")
                    parts.append(f"{name} : {ty}")

                parts.append(f"⊢ {goal}")
                all_states.append("\n".join(parts))

        if not all_states:
            return "No goal states found in Jixia output."

        return all_states[-1]
