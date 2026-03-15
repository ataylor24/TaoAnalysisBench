import os
import json
from typing import List, Dict, Any

BASE_RESULT_PATH = "/Users/alextaylor/Desktop/lean_prover/output/union_verified_theorems.jsonl"
MAIN_RESULT_PATH = "/Users/alextaylor/Desktop/lean_prover/src/agent/output_jixia_agent/verification_results.json"
RETRY_PATHS = [
    "/Users/alextaylor/Desktop/lean_prover/src/agent/output_successful_retry_0/verification_results.json",
    "/Users/alextaylor/Desktop/lean_prover/src/agent/output_successful_retry_1/verification_results.json",
    "/Users/alextaylor/Desktop/lean_prover/src/agent/output_successful_retry_2/verification_results.json"
]

OUTPUT_DIR = "/Users/alextaylor/Desktop/lean_prover/output/collated_results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_jsonl(file_path: str) -> List[Dict[str, Any]]:
    with open(file_path, "r") as f:
        return [json.loads(line) for line in f]

def load_json(file_path: str) -> List[Dict[str, Any]]:
    with open(file_path, "r") as f:
        return json.load(f)

def main():
    base_data = load_jsonl(BASE_RESULT_PATH)
    updated_data = load_json(MAIN_RESULT_PATH)
    for retry_path in RETRY_PATHS:
        updated_data.extend(load_json(retry_path))
    keys = ['index', 'chapter_name', 'FQN', 'content']
    
    collated_data = []
    FQN_set = set()
    all_fqns = set()
    idx = 0
   
    for item in base_data + updated_data:
        all_fqns.add(item["FQN"])
        if (item["status"] == "error" or item["returncode"] != 0) or item["FQN"] in FQN_set:
            continue
        
        FQN_set.add(item["FQN"])
        if not "index" in item:
            item["index"] = idx
            idx += 1
        else:
            item["index"] = idx
            idx += 1
        item_dict = {key: item[key] for key in keys if key in item}
        
        collated_data.append(item_dict)
    
    with open(os.path.join(OUTPUT_DIR, "collated_results.jsonl"), "w") as f:
        for item in collated_data:
            f.write(json.dumps(item) + "\n")


if __name__ == "__main__":
    main()