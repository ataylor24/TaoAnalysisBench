from typing import List, Dict, Any
import json
import os
from globals import ANALYSIS_BOOK_DIRECTORY
from pathlib import Path

def file_look_up(chapter_name: str) -> str:
    with open(os.path.join(ANALYSIS_BOOK_DIRECTORY, chapter_name + ".lean"), "r") as f:
        return f.read()
    
def load_jsonl(file_path: str) -> List[Dict[str, Any]]:
    with open(file_path, "r") as f:
        return [json.loads(line) for line in f]
    

def load_json(file_path: str) -> Dict[str, Any]:
    with open(file_path, "r") as f:
        return json.load(f)  
    
    
def write_jsonl(output_dir: str, data: List[Dict[str, Any]]):
    with open(os.path.join(output_dir, "results.jsonl"), "w") as f:
        for item in data:
            f.write(json.dumps(item, indent=4) + "\n")
            
            
def write_human_readable(output_dir: str, results: Dict[str, Any]):
    with open(os.path.join(output_dir, "human_readable.txt"), "w") as f:
        for result in results:
            f.write(result["chapter_name"] + ": " + result["FQN"] + "\n\n" + extract_code_block(result["pretty"]) + "\n\n")
            f.write("-----------------------------------\n\n")
            

def construct_data(dataset: List[Dict[str, Any]], verification_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    unverified_data = []
    
    dataset_dict = {idx: query for idx, query in enumerate(dataset)}
    results_dict = {result["index"]: result for result in verification_results}
    
    for index in sorted(dataset_dict.keys()):
        if index in results_dict:
            unverified_data.append({**dataset_dict[index]})
    return unverified_data
            

def construct_query(query: Dict[str, Any]) -> str:
    message = (f"We would like to construct a compilable version of a theorem from {query['chapter_name']}. The theorem is as follows:\n{query['content']}\n"
    "Please use the following relevant lean files to aggregate the minimum number of statements required to compile the theorem. Please include all necessary imports and properly construct the namespace(s) required for compilation."
    "Do not change the theorem name and do not solve the theorem. You may include necessary external imports, but do not import sections from the textbook provided below or others in the textbook.\n"
    "Do not use placeholders or dummy definitions to aid compilation. You must use the actual definitions and theorems from the relevant lean files to compile the theorem."
    "The relevant lean files are as follows:\n" + query['dependency_set'] + "\n"
    "Please return the compiled theorem in a valid lean code block wrapped in ```lean tags."
    )
    return message

def construct_agentic_query(query: Dict[str, Any]) -> str:
    source_file = file_look_up(query["chapter_name"])
    message = (
        f"We would like to construct a self-contained, compilable version of a theorem from "
        f"{query['chapter_name']}. The theorem is as follows:\n{query['query_text']}\n"
        "\n"
        "Requirements:\n"
        "- Include all necessary imports and properly construct the namespace(s) required for compilation.\n"
        "- Do NOT change the theorem name and do NOT solve the theorem; the proof must remain 'by sorry'.\n"
        "- You may include necessary external Mathlib imports (e.g. Mathlib.Tactic), but you must NOT import\n"
        f"  '{query['chapter_name']}' itself or any other textbook section files (e.g. 'Analysis.Section_11_*').\n"
        "\n"
        "We provide you with the source Lean file for this chapter. This file contains the authoritative\n"
        f"definitions and theorems that your snippet must be consistent with:\n"
        f"----- BEGIN SOURCE {query['chapter_name']} -----\n"
        f"{source_file}\n"
        f"----- END SOURCE {query['chapter_name']} -----\n"
        "\n"
        "We also provide a summary of statements from previous chapters that are relevant for compilation.\n"
        "These are for reference only, to tell you which names exist and where they come from; they are NOT\n"
        "guaranteed to be valid Lean code. When you need one of these definitions or theorems, you must obtain\n"
        "its exact Lean declaration from the actual source file (using the file_look_up_tool) and copy it\n"
        "verbatim into your snippet.\n"
        "\n"
        "Reference summary of required statements:\n"
        f"{query['content']}\n"
        "\n"
        "Hard constraints:\n"
        "- You must NOT introduce placeholder or dummy definitions (e.g. 'def foo := 0', 'abbrev bar := 0',\n"
        "  ':= fun _ => 0') for any symbol that is part of the textbook.\n"
        "- You must NOT change the types or meanings of existing textbook definitions; you may only copy them\n"
        "  as they appear in the source files.\n"
        "- The ONLY allowed 'sorry' in the final snippet is the one in the target theorem given above. All\n"
        "  earlier definitions and supporting lemmas must be fully defined.\n"
        "\n"
        "You may use the look-up tool to fetch the exact syntax of any needed declarations, but you must not\n"
        "alter their types or bodies.\n"
        "\n"
        "Please return the final Lean snippet, including all necessary supporting definitions, in a single\n"
        "valid Lean code block wrapped in ```lean tags.\n"
    )
    return message


def construct_agentic_query_v2(query: Dict[str, Any]) -> str:
    source_file = file_look_up(query["chapter_name"])
    dependency_set = "[" + ", ".join(sorted([Path(dep).name for dep in query["dependency_set"]])) + "]"
    message = f"""
We need a **self-contained, compilable Lean snippet** for the following theorem
from {query['chapter_name']}:

----- TARGET THEOREM -----
{query['query_text']}
--------------------------

----- DEPENDENCY SET -----
{dependency_set}
--------------------------

Your job is NOT to design new mathematics. Your job is to EXTRACT a faithful,
dependency-minimal slice of the textbook’s Lean code so that the **target theorem**
parses and typechecks **in isolation**, in a fresh Lean + Mathlib project, **WITHOUT**
importing any `Analysis.Section_*` modules.

You must implement the following constraints:

============================================================
CORE RULES FOR BUILDING THE SELF-CONTAINED SNIPPET (V4)
============================================================

1. **Usage-based dependency rule**
   Build the USED NAME SET consisting of:
   - Every non-notation name in the target theorem's statement.
   - Every name appearing in the *transitive dependency* of included declarations
     required for parsing / typechecking / instance resolution / coercions / notation.

2. **For every textbook symbol in the USED NAME SET**, you must:
   - Obtain its **exact declaration** from the real source (the chapter file below,
     or any earlier section via `file_look_up_tool`).
   - **Copy its Lean code verbatim**: type, body, attributes, proofs, and any `sorry`
     present in the textbook.
   - NEVER synthesize definitions from the summary below.

3. **The reference summary provided is documentation only.**
   - It may tell you *which* names exist, but *none* of its code may be used.
   - If you need a declaration, fetch its *actual* source file and copy it exactly.

4. **Handling textbook tactic proofs (e.g. by aesop, grind, simp, etc.)**
   - If feasible, copy the tactic proof term **exactly** and include any dependent
     textbook lemmas/instances (verbatim).
   - If including those dependencies excessively enlarges the snippet, you may replace
     the **proof term only** with `by sorry`, *but only for theorems/lemmas*.
   - You may NEVER `sorry` the bodies of definitions/structures/instances.

5. **Forbidden behaviors**
   - No placeholder implementations for textbook names (`:= 0`, `:= fun _ => 0`, etc.).
   - No redefining textbook objects (e.g. replacing quotient-based `Real` with ℚ).
   - No changing the signature of any textbook declaration.
   - No synthesized or “simplified” versions of textbook interfaces.
   - No “I give up” headers or meta explanations.

6. **Imports**
   - You may import relevant Mathlib modules (`Mathlib.Tactic`, `Mathlib.Data.Real.Basic`, …).
   - You must NOT import ANY textbook section (no `Analysis.Section_*`).

7. **Target theorem**
   - Must retain EXACT name and statement.
   - Must end with `by sorry` unless explicitly instructed otherwise.

8. **Final output**
   - A SINGLE Lean file, inside one ```lean code block.
   - No natural-language text before or after the code block.
   - The snippet must be self-contained and compilable under the pinned Mathlib/Lean version.

============================================================
AUTHORITATIVE SOURCE FOR THIS CHAPTER
============================================================
----- BEGIN SOURCE {query['chapter_name']} -----
{source_file}
----- END SOURCE {query['chapter_name']} -----

============================================================
REFERENCE SUMMARY (FOR INFORMATION ONLY — DO NOT COPY CODE)
============================================================
{query['content']}
============================================================

Construct the final Lean snippet accordingly.
"""

    return message


def extract_code_block(content: str) -> str:
    try:
        if "```lean" in content:
            return content.split("```lean", 1)[1].split("```", 1)[0].strip()
        if "```" in content:
            return content.split("```", 1)[1].split("```", 1)[0].strip()
        return content.strip()
    except Exception:
        return content.strip()
    

def filter_baseline(baseline_data):
    aggregated_data = {}
    for idx, item in enumerate(baseline_data):
        if item["chapter_name"] not in aggregated_data:
            aggregated_data[item["chapter_name"]] = []
        aggregated_data[item["chapter_name"]].append({
            "idx": idx,
            "content": item["content"].strip()
        })
    return aggregated_data 

def sort_by_section(sections: list) -> list:
    return sorted(sections, key=lambda x: (int(x.split("_")[1]), x.split("_")[2].split(".")[0]))
