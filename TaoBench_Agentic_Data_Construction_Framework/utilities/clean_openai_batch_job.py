import json
import argparse
from typing import List, Dict, Any

BASE_DATA_PATH = "/Users/alextaylor/Desktop/lean_prover/output/collated_results/tao_analysis_baseline.jsonl"

def resolve_fqn_prompt_mapping(base_data: List[Dict[str, Any]]) -> Dict[str, str]:
    fqn_prompt_mapping = {}
    for item in base_data:
        fqn_prompt_mapping[item["FQN"]] = item["content"]
    return fqn_prompt_mapping

def load_jsonl(file_path: str) -> List[Dict[str, Any]]:
    with open(file_path, "r") as f:
        return [json.loads(line) for line in f]
    
def save_jsonl(data: List[Dict[str, Any]], file_path: str):
    with open(file_path, "w") as f:
        for item in data:
            f.write(json.dumps(item) + "\n")

def clean_output(output: str) -> str:
    return output.replace("```lean", "").replace("```lean4", "").replace("```", "")

def clean_openai_batch_job(data: List[Dict[str, Any]], base_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    fqn_prompt_mapping = resolve_fqn_prompt_mapping(base_data)
    
    cleaned_data_dict = {}
    for item in data:
        problem_fqn = item["custom_id"].split("__")[0]
        if problem_fqn not in cleaned_data_dict:
            cleaned_data_dict[problem_fqn] = {
                "problem_fqn": problem_fqn,
                "prompt": fqn_prompt_mapping[problem_fqn],
                "proofs": []
            }
        
        full_output = item["response"]["body"]["output"][1]["content"][0]["text"]
        cleaned_output = clean_output(full_output)
        cleaned_data_dict[problem_fqn]["proofs"].append({
            "full_output": full_output,
            "cleaned_output": cleaned_output
        })
        
    return list(cleaned_data_dict.values())

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_path", type=str, required=True)
    parser.add_argument("--output_path", type=str, required=True)
    args = parser.parse_args()

    raw_data = load_jsonl(args.input_path)
    base_data = load_jsonl(BASE_DATA_PATH)
    cleaned_data = clean_openai_batch_job(raw_data, base_data)
    save_jsonl(cleaned_data, args.output_path)