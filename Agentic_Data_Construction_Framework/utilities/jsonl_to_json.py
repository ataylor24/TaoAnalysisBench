import json
import argparse
import os

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("jsonl_path", type=str)
    args = parser.parse_args()
    jsonl_to_json(args.jsonl_path)

def jsonl_to_json(jsonl_path: str):
    json_path = os.path.join(os.path.dirname(jsonl_path), "json_" + os.path.basename(jsonl_path).replace(".jsonl", ".json"))
    with open(jsonl_path, "r") as f:
        data = [json.loads(line) for line in f]
    with open(json_path, "w") as f:
        f.write(json.dumps(data, indent=4) + "\n")

if __name__ == "__main__":
    main()