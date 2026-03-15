#!/usr/bin/env python3
import os
import json
import argparse
from openai import OpenAI

# ---- CONFIG ----
DEFAULT_EVAL_FILE = (
    "/path/"
    "TaoBench_TaoBenchMathlib.jsonl"
)
DEFAULT_BATCH_FILE = (
    "/path/"
    "GPT_batch_input.jsonl"
)


# GPT-5.1 (Thinking) via Responses API
MODEL_NAME = "gpt-5.1"

N_SAMPLES_PER_PROBLEM = 8


def format_prompt(problem: dict, model: str, COT: bool) -> str:

    code = problem.get("TaoBenchMathlib", "").replace("sorry", "").rstrip()
    fqn = problem.get("FQN")

    if COT:
        prompt = (
            f"Complete the following Lean 4 code for the theorem: {fqn}. "
            "Return your answer inside a ```lean4 fenced block.\n\n"
            f"```lean4\n{code}\n```"
            "Before producing the Lean 4 code to formally prove the given theorem, "
            "provide a detailed proof plan outlining the main proof steps and strategies. "
            "The plan should highlight key ideas, intermediate lemmas, and proof structures "
            "that will guide the construction of the final formal proof."
        )
    else:
        raise ValueError("Here!")

    return prompt


def build_batch_jsonl(eval_path: str, batch_path: str) -> None:
    """
    Build Batch API JSONL where each line is a /v1/responses request using GPT-5.1.

    - Uses Responses API schema (input, max_output_tokens, reasoning).
    - Duplicates each problem N_SAMPLES_PER_PROBLEM times instead of using `n`,
      because Responses API does not support multiple completions in one call.
    """
    records = []
    total_requests = 0

    with open(eval_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)

            fqn = row["FQN"]
            prompt = format_prompt(row, MODEL_NAME, COT=True)

            # Create N_SAMPLES_PER_PROBLEM separate requests per theorem
            for k in range(N_SAMPLES_PER_PROBLEM):
                custom_id = f"{fqn}__sample_{k}"

                record = {
                    "custom_id": custom_id,
                    "method": "POST",
                    "url": "/v1/responses",
                    "body": {
                        "model": MODEL_NAME,
                        # Responses API: `input` instead of `messages`
                        "input": [
                            {
                                "role": "user",
                                "content": prompt,
                            }
                        ],
                        "reasoning": {
                            "effort": "medium"
                        },
                    },
                }
                records.append(record)
                total_requests += 1
            

    with open(batch_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(
        f"Wrote {len(records)} batch records to {batch_path} "
        f"({total_requests} total requests)."
    )


def upload_and_create_batch(batch_path: str):
    """
    Upload the JSONL file and create a Batch job pointing at /v1/responses.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set.")
    client = OpenAI(api_key=api_key)


    # Upload file for batch
    with open(batch_path, "rb") as f:
        batch_file = client.files.create(
            file=f,
            purpose="batch",
        )
    print(f"Uploaded batch file: {batch_file.id} ({batch_file.filename})")

    # Create the batch job; endpoint must match the per-record `url`
    batch_job = client.batches.create(
        input_file_id=batch_file.id,
        endpoint="/v1/responses",
        completion_window="24h",
    )
    print("Created batch job:")
    print(f"  id: {batch_job.id}")
    print(f"  status: {batch_job.status}")
    print(f"  input_file_id: {batch_job.input_file_id}")

    return batch_job


def main():
    parser = argparse.ArgumentParser(
        description="Build and submit an OpenAI Batch job for Lean proofs using GPT-5.1 Responses API."
    )
    parser.add_argument(
        "--eval-file",
        default=DEFAULT_EVAL_FILE,
        help=f"Input evaluation JSONL (default: {DEFAULT_EVAL_FILE})",
    )
    parser.add_argument(
        "--batch-file",
        default=DEFAULT_BATCH_FILE,
        help=f"Output batch input JSONL (default: {DEFAULT_BATCH_FILE})",
    )
    args = parser.parse_args()

    build_batch_jsonl(args.eval_file, args.batch_file)
    upload_and_create_batch(args.batch_file)


if __name__ == "__main__":
    main()
