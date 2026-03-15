#!/usr/bin/env python3
import os
import json
import argparse
import time

from google import genai
from google.genai import types

# ---- CONFIG ----

Now_Name = "GPT_Convert_Pipeline_Result_CleanAnnotation_TaoAristotleChecked_CorrectOrder_part4"

DEFAULT_EVAL_FILE = (
    "/path/"
    "TaoBench_TaoBenchMathlib.jsonl"
)
DEFAULT_BATCH_FILE = (
    "/path/"
    "gemini_batch_input.jsonl"
)

# Gemini 3 Pro 
MODEL_NAME = "models/gemini-3-pro-preview"

N_SAMPLES_PER_PROBLEM = 8

THINKING_LEVEL = "high"   



def format_prompt(problem: dict, model: str, COT: bool) -> str:

    code = problem.get("TaoBench", "").replace("sorry", "").rstrip()
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
            f"Provide the proof of the theorem {fqn} in a ```lean4 fenced code block. Do not introduce any new local definitions."
        )
    else:
        raise ValueError("Here!")

    return prompt


def build_batch_jsonl(eval_path: str, batch_path: str) -> None:

    total_requests = 0

    with open(eval_path, "r", encoding="utf-8") as fin, open(batch_path, "w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)

            fqn = row["FQN"]
            prompt = format_prompt(row, MODEL_NAME, COT=True)

            for k in range(N_SAMPLES_PER_PROBLEM):
                key = f"{fqn}__sample_{k}"

                req = {
                    "contents": [
                        {
                            "role": "user",
                            "parts": [{"text": prompt}],
                        }
                    ],
                    "generation_config": {
                            "thinking_config": {
                                "include_thoughts": True
                            },
                        }
                }

                record = {
                    "key": key,
                    "request": req,
                }

                fout.write(json.dumps(record, ensure_ascii=False) + "\n")
                total_requests += 1

    print(f"Wrote {total_requests} Gemini batch records to {batch_path}.")


def upload_and_create_batch(batch_path: str, display_name: str = "lean-proof-batch"):

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY (or GOOGLE_API_KEY) env var first.")

    client = genai.Client(api_key=api_key)

    uploaded_file = client.files.upload(
        file=batch_path,
        config=types.UploadFileConfig(
            display_name=display_name,
            mime_type="jsonl",
        ),
    )
    print(f"Uploaded batch file: {uploaded_file.name}")

    batch_job = client.batches.create(
        model=MODEL_NAME,
        src=uploaded_file.name,
        config={"display_name": display_name},
    )
    print("Created batch job:")
    print(f"  name:   {batch_job.name}")
    print(f"  state:  {batch_job.state.name}")

    return client, batch_job


def poll_and_download_results(client, job_name: str, out_path: str, poll_interval_sec: int = 30):

    completed = {
        "JOB_STATE_SUCCEEDED",
        "JOB_STATE_FAILED",
        "JOB_STATE_CANCELLED",
        "JOB_STATE_EXPIRED",
    }

    print(f"Polling status for job: {job_name}")
    job = client.batches.get(name=job_name)
    while job.state.name not in completed:
        print(f"  state={job.state.name} ...")
        time.sleep(poll_interval_sec)
        job = client.batches.get(name=job_name)

    print(f"Job finished with state: {job.state.name}")
    if job.state.name != "JOB_STATE_SUCCEEDED":
        if getattr(job, "error", None):
            print(f"Error: {job.error}")
        return None

    if not job.dest or not job.dest.file_name:
        print("No result file found in job.dest.file_name")
        return None

    result_file_name = job.dest.file_name
    print(f"Results are in file: {result_file_name}")

    content_bytes = client.files.download(file=result_file_name)
    with open(out_path, "wb") as f:
        f.write(content_bytes)

    print(f"Saved results to: {out_path}")
    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="Build and submit a Gemini Batch job for Lean proofs using Gemini 3 Pro."
    )
    parser.add_argument("--eval-file", default=DEFAULT_EVAL_FILE)
    parser.add_argument("--batch-file", default=DEFAULT_BATCH_FILE)
    parser.add_argument(
        "--download-results-to",
        default=None,
        help="If set, will poll job and download results JSONL to this path.",
    )
    args = parser.parse_args()

    build_batch_jsonl(args.eval_file, args.batch_file)
    client, job = upload_and_create_batch(args.batch_file, display_name="lean-proof-batch")

    if args.download_results_to:
        poll_and_download_results(client, job.name, args.download_results_to)


if __name__ == "__main__":
    main()
