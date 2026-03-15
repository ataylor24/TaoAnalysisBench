#!/usr/bin/env python3
import os
import json
import argparse
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm


from openai import OpenAI

# ---- DEFAULT PATHS ----
DEFAULT_EVAL_FILE = (
    "/path/"
    "TaoBench_TaoBenchMathlib.jsonl"
)

DEFAULT_OUT_FILE = (
    "/path/"
    "your_file_path.jsonl"
)

# DeepSeek OpenAI-compatible base_url
DEEPSEEK_BASE_URL = "https://api.deepseek.com"  # official docs :contentReference[oaicite:2]{index=2}

# “DeepSeek-V3.2 (Thinking Mode)” recommended: deepseek-chat + thinking enabled

DEFAULT_MODEL = "deepseek-chat"
# DEFAULT_MODEL = "deepseek-reasoner"
DEFAULT_N_SAMPLES = 8


def format_prompt(problem: dict, COT: bool = True) -> str:
    code = problem.get("TaoBenchMathlib", "").replace("sorry", "").rstrip()
    fqn = problem.get("FQN", "")

    if COT:
        prompt = (
            f"Complete the following Lean 4 code for the theorem: {fqn}. "
            "Return your answer inside a ```lean4 fenced block.\n\n"
            f"```lean4\n{code}\n```"
            "Before producing the Lean 4 code to formally prove the given theorem, "
            "provide a detailed proof plan outlining the main proof steps and strategies. "
            "The plan should highlight key ideas, intermediate lemmas, and proof structures "
            "that will guide the construction of the final formal proof."
            # f"Provide the proof of the theorem {fqn} in a ```lean4 fenced code block. Do not introduce any new local definitions."
        )
    else:
        raise ValueError("Here!")
        
    return prompt


def make_client() -> OpenAI:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY environment variable is not set.")

    return OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)


def call_deepseek(prompt: str, model: str, thinking_enabled: bool, max_tokens: int, retry: int = 5):
    """
    Uses DeepSeek Chat Completion API (OpenAI-compatible).
    Thinking Mode:
      - model="deepseek-chat" + extra_body={"thinking":{"type":"enabled"}}  :contentReference[oaicite:3]{index=3}
      - or model="deepseek-reasoner" (no extra_body needed)              :contentReference[oaicite:4]{index=4}
    Output includes reasoning_content when thinking is enabled.           :contentReference[oaicite:5]{index=5}
    """
    client = make_client()

    messages = [{"role": "user", "content": prompt}]

    extra_body = None
    # If you want "V3.2 thinking mode" on deepseek-chat, pass thinking switch
    if model == "deepseek-chat":
        extra_body = {"thinking": {"type": "enabled" if thinking_enabled else "disabled"}}

    last_err = None
    for attempt in range(retry):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                # temperature/top_p may be ignored in thinking mode per docs :contentReference[oaicite:6]{index=6}
                extra_body=extra_body if extra_body else None,
            )
            msg = resp.choices[0].message
            return {
                "content": getattr(msg, "content", None),
                "reasoning_content": getattr(msg, "reasoning_content", None),
                "finish_reason": resp.choices[0].finish_reason,
                "usage": getattr(resp, "usage", None),
                "raw": resp.model_dump() if hasattr(resp, "model_dump") else None,
            }
        except Exception as e:
            last_err = e
            # simple exponential backoff
            sleep_s = min(2 ** attempt, 30)
            time.sleep(sleep_s)
    raise last_err


def load_done_ids(out_path: str) -> set:
    done = set()
    if not os.path.exists(out_path):
        return done
    with open(out_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                cid = obj.get("custom_id")
                if cid:
                    done.add(cid)
            except Exception:
                continue
    return done


def main():
    parser = argparse.ArgumentParser(
        description="Run DeepSeek-V3.2 Thinking Mode (no Batch) for Lean proofs."
    )
    parser.add_argument("--eval-file", default=DEFAULT_EVAL_FILE)
    parser.add_argument("--out-file", default=DEFAULT_OUT_FILE)
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help='deepseek-chat (recommended for V3.2 thinking toggle) or deepseek-reasoner')
    parser.add_argument("--thinking", action="store_true", default=True,
                        help="Enable thinking mode (for deepseek-chat via thinking switch).")
    parser.add_argument("--no-thinking", dest="thinking", action="store_false",
                        help="Disable thinking mode (only affects deepseek-chat).")
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--n-samples", type=int, default=DEFAULT_N_SAMPLES)
    parser.add_argument("--workers", type=int, default=4, help="Thread workers (no batch).")
    parser.add_argument("--resume", action="store_true", help="Skip already finished custom_id in out-file.")
    args = parser.parse_args()

    # sanity: model choices per docs :contentReference[oaicite:7]{index=7}
    if args.model not in ("deepseek-chat", "deepseek-reasoner"):
        raise ValueError('model must be "deepseek-chat" or "deepseek-reasoner"')

    done_ids = load_done_ids(args.out_file) if args.resume else set()
    write_lock = threading.Lock()

    def submit_one(row: dict, sample_idx: int):
        fqn = row.get("FQN", "UNKNOWN")
        custom_id = f"{fqn}__sample_{sample_idx}"
        if args.resume and custom_id in done_ids:
            return None

        prompt = format_prompt(row, COT=True)
        result = call_deepseek(
            prompt=prompt,
            model=args.model,
            thinking_enabled=args.thinking,
            max_tokens=args.max_tokens,
        )
        out_obj = {
            "custom_id": custom_id,
            "FQN": fqn,
            "sample_idx": sample_idx,
            "model": args.model,
            "thinking": args.thinking if args.model == "deepseek-chat" else True,
            "reasoning_content": result["reasoning_content"],
            "content": result["content"],
            "finish_reason": result["finish_reason"],
            # "usage": result["usage"],
            "usage": (result["usage"].model_dump() if result["usage"] is not None else None),
        }
        # write line (thread-safe)
        with write_lock:
            with open(args.out_file, "a", encoding="utf-8") as wf:
                wf.write(json.dumps(out_obj, ensure_ascii=False) + "\n")
        return custom_id

    # read eval jsonl
    rows = []
    with open(args.eval_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    # dispatch
    futures = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for row in rows:
            for k in range(args.n_samples):
                futures.append(ex.submit(submit_one, row, k))

        finished = 0
        skipped = 0
        failed = 0
        with tqdm(total=len(futures), desc="DeepSeek", unit="req") as pbar:
            for fu in as_completed(futures):
                try:
                    cid = fu.result()
                    if cid is None:
                        skipped += 1
                    else:
                        finished += 1
                except Exception as e:
                    # log error (don’t crash entire run)
                    failed += 1
                    with write_lock:
                        with open(args.out_file + ".errors.log", "a", encoding="utf-8") as ef:
                            ef.write(str(e) + "\n")
                pbar.update(1)
                pbar.set_postfix(ok=finished, skipped=skipped, failed=failed)

    print(f"Done. wrote={finished}, skipped={skipped}, out={args.out_file}")


if __name__ == "__main__":
    main()
