#!/usr/bin/env python3
"""
Compare two verification_results.json files.

Outputs a CSV comparing compile success per problem and prints a short summary
of which problems were solved uniquely per approach vs. shared overlap.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import os
from pathlib import Path
from typing import Dict, List, Tuple


def load_results(path: Path) -> Dict[int, dict]:
    """Return a mapping from problem index to result entry."""
    with path.open() as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path} does not contain a list")
    results: Dict[int, dict] = {}

    for entry in data:
        
        idx = entry.get("index")
        if idx is None:
            raise ValueError(f"Entry without index in {path}: {entry}")
        results[idx] = entry
    print(len(data), len(results))
    return results


def compiled_ok(entry: dict | None) -> bool:
    """Treat status ok + returncode==0 (or missing) as compiled."""
    if not entry:
        return False
    status_ok = entry.get("status") == "ok"
    returncode = entry.get("returncode")
    rc_ok = returncode in (None, 0)
    return status_ok and rc_ok


def get_theorems_from_set(_set: set[int], res: Dict[int, dict]) -> List[int]:
    return {idx: res[idx] for idx in _set}

def build_csv_rows(
    idxs: List[int],
    res_a: Dict[int, dict],
    res_b: Dict[int, dict],
    label_a: str,
    label_b: str,
) -> Tuple[List[dict], Dict[str, List[int]], List[str]]:
    rows: List[dict] = []
    solved_a: List[int] = []
    solved_b: List[int] = []
    unverified_a: List[int] = []
    unverified_b: List[int] = []
    headers = [
        "problem_index",
        f"{label_a}_status",
        f"{label_a}_compiled",
        f"{label_b}_status",
        f"{label_b}_compiled",
    ]
    for idx in idxs:
        entry_a = res_a.get(idx)
        entry_b = res_b.get(idx)
        a_ok = compiled_ok(entry_a)
        b_ok = compiled_ok(entry_b)
        if a_ok:
            solved_a.append(idx)
        else:
            unverified_a.append(idx)
        
        if b_ok:
            solved_b.append(idx)
        else:
            unverified_b.append(idx)
        rows.append(
            {
                "problem_index": idx,
                f"{label_a}_status": entry_a.get("status") if entry_a else "missing",
                f"{label_a}_compiled": a_ok,
                f"{label_b}_status": entry_b.get("status") if entry_b else "missing",
                f"{label_b}_compiled": b_ok,
            }
        )

    only_a = sorted(set(solved_a) - set(solved_b))
    only_b = sorted(set(solved_b) - set(solved_a))
    overlap = sorted(set(solved_a) & set(solved_b))
    summary: Dict[str, List[int]] = {
        f"{label_a}_only": (only_a),
        f"{label_b}_only": only_b,
        "overlap": overlap,
    }
    
    unverified_overlap = set(unverified_a) & set(unverified_b)
    unverified_theorems = get_theorems_from_set(unverified_overlap, res_a)
    
    
    verified_theorems = get_theorems_from_set(set(solved_a), res_a)
    verified_theorems.update(get_theorems_from_set(set(solved_b), res_b))
    
    return rows, summary, headers, verified_theorems, unverified_theorems


def write_csv(rows: List[dict], headers: List[str], output_path: Path | None) -> None:
    if output_path:
        with output_path.open("w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
    else:
        writer = csv.DictWriter(sys.stdout, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare two verification_results.json files."
    )
    parser.add_argument("results_a", type=Path, help="First verification_results file")
    parser.add_argument("results_b", type=Path, help="Second verification_results file")
    parser.add_argument(
        "--label-a",
        default="approach_a",
        help="Label for the first approach (used in CSV column names)",
    )
    parser.add_argument(
        "--label-b",
        default="approach_b",
        help="Label for the second approach (used in CSV column names)",
    )
    parser.add_argument(
        "--csv-output",
        type=Path,
        default=None,
        help="Optional path to write the CSV (prints to stdout if omitted)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    res_a = load_results(args.results_a)
    res_b = load_results(args.results_b)
    


    print(sorted([e for e in res_b]))
    all_idxs = sorted(set(res_a) | set(res_b))
    rows, summary, headers, verified_theorems, unverified_theorems = build_csv_rows(
        all_idxs, res_a, res_b, args.label_a, args.label_b
    )
    write_csv(rows, headers, args.csv_output)

    total = len(all_idxs)
    print(f"Compared {total} problems.")
    print(f"{args.label_a} solved: {len(summary[f'{args.label_a}_only']) + len(summary['overlap'])}")
    print(f"{args.label_b} solved: {len(summary[f'{args.label_b}_only']) + len(summary['overlap'])}")
    print("Summary (problem indices):")
    for key, values in summary.items():
        print(f"  {key}: {len(values)}")
    
    with open(os.path.join("../output", "union_verified_theorems.jsonl"), "w") as f:
        for idx, theorem_info in verified_theorems.items():
            f.write(json.dumps({"index": idx, **theorem_info}) + "\n")
    
    with open(os.path.join("../output", "union_unverified_theorems.jsonl"), "w") as f:
        for idx, theorem_info in unverified_theorems.items():
            f.write(json.dumps({"index": idx, **theorem_info}) + "\n")


if __name__ == "__main__":
    main()
