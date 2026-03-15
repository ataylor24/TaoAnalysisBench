# run_baseline.py
import os, json, argparse
from pathlib import Path
from typing import Dict, List
from openai import OpenAI
from vllm import LLM, SamplingParams
from tqdm import tqdm
import torch

# --------------------------
# Data loading
# --------------------------
def load_jsonl(path: str) -> List[Dict]:
    """Return list of problems (one dict per line)."""
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            dp = json.loads(line)
            data.append(dp)
    return data

# --------------------------
# Prompting
# --------------------------
def format_prompt(problem: Dict, model: str, COT: bool) -> str:

    code = problem.get("TaoBench").strip()

    FQN = problem.get("FQN").strip()

    if COT == "True" and model == "deepseek-ai/DeepSeek-Prover-V2-7B":

        prompt = (
        f"Complete the following Lean 4 code for the theorem: {FQN}:\n\n"
        f"```lean4\n{code}\n```"
        "\n\nBefore producing the Lean 4 code to formally prove the given theorem, provide a detailed proof plan outlining the main proof steps and strategies."
        "\nThe plan should highlight key ideas, intermediate lemmas, and proof structures that will guide the construction of the final formal proof."
        )

    elif COT == "False" and model == "deepseek-ai/DeepSeek-Prover-V2-7B":
        prompt = (
            f"Complete the following Lean 4 code for the theorem: {FQN}:\n\n"
            f"```lean4\n{code}\n```"
        )

    elif model == "Goedel-LM/Goedel-Prover-V2-8B":
        prompt = (
        f"Complete the following Lean 4 code for the theorem: {FQN}:\n\n"
        f"```lean4\n{code}\n```"
        "\n\nBefore producing the Lean 4 code to formally prove the given theorem, provide a detailed proof plan outlining the main proof steps and strategies."
        "\nThe plan should highlight key ideas, intermediate lemmas, and proof structures that will guide the construction of the final formal proof."
        )

    elif model == "Goedel-LM/Goedel-Prover-V2-32B":
        prompt = (
        f"Complete the following Lean 4 code for the theorem: {FQN}:\n\n"
        f"```lean4\n{code}\n```"
        "\n\nBefore producing the Lean 4 code to formally prove the given theorem, provide a detailed proof plan outlining the main proof steps and strategies."
        "\nThe plan should highlight key ideas, intermediate lemmas, and proof structures that will guide the construction of the final formal proof."
        )

    elif model == "AI-MO/Kimina-Prover-Distill-8B":
        prompt = (
        f"Think about and solve the theorem {FQN} step by step in Lean 4.\n"
        f"# Formal statement:\n```lean4\n{code}\n```\n"
        )

    else:
        raise ValueError("Here!!")

    print(prompt)
    print(COT)
    print(model)

    return prompt

def extract_lean_block(text: str) -> str:
    """Pull the last ```lean4 ... ``` block or best-effort fallback."""
    if "```lean4" in text:
        tail = text.split("```lean4")[-1]
        return tail.split("```", 1)[0].strip()
    return text.strip()

# --------------------------
# Backends
# --------------------------
def run_vllm_local(
    model_id: str,
    prompts: List[str],
    n: int,
    max_tokens: int,
    temperature: float,
    outdir: str,
    tensor_parallel_size: int = 1,
    gpu_mem_util: float = 0.9,
    max_model_len: int = 8192,
) -> List[Dict]:
    
    answers_file = outdir
    os.makedirs(os.path.dirname(answers_file), exist_ok=True)
    ans_file = open(answers_file, "w")

    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_id, use_fast=True)

    llm = LLM(
        model=model_id,
        dtype="float16",
        tensor_parallel_size=tensor_parallel_size,
        gpu_memory_utilization=gpu_mem_util,
        max_model_len=max_model_len,
    )
    sampling = SamplingParams(max_tokens=max_tokens, temperature=temperature, n=n)

    results: List[Dict] = []

    for i, prompt in enumerate(tqdm(prompts, desc="Generation (vLLM)")):
        print("processing prompt", i)

        inputs = prompt
        # be defensive if eos token is missing
        eos_tok = getattr(tokenizer, "eos_token", None)
        if eos_tok:
            inputs = inputs.replace(eos_tok, "")

        with torch.inference_mode():
            outs = llm.generate(inputs, sampling_params=sampling)

        proofs = []
        for gen in outs[0].outputs:
            full = gen.text
            cleaned = extract_lean_block(full)
            proofs.append({"full_output": full, "cleaned_proof": cleaned})
        
        now_Answer = {"idx": i, "prompt": prompt, "proofs": proofs}
        ans_file.write(json.dumps(now_Answer) + "\n")
        ans_file.flush()

        results.append({"idx": i, "prompt": prompt, "proofs": proofs})

    ans_file.close()
    
    return results

def make_openai_client(api_type: str) -> OpenAI:
    """
    api_type: 'openai' (GPT-5) or 'deepseek'
    Requires:
      - OPENAI_API_KEY for openai
      - DEEPSEEK_API_KEY for deepseek
    """
    if api_type == "openai":
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError("Missing OPENAI_API_KEY")
        return OpenAI(api_key=key, timeout=600)

    if api_type == "deepseek":
        key = os.getenv("DEEPSEEK_API_KEY")
        if not key:
            raise ValueError("Missing DEEPSEEK_API_KEY")
        return OpenAI(api_key=key, base_url="https://api.deepseek.com", timeout=600)

    raise ValueError(f"Unknown api_type={api_type}")

def run_openai_api(
    api_type: str,
    model_name: str,
    prompts: List[str],
    n: int,
    max_tokens: int,
    temperature: float,
) -> List[Dict]:
    client = make_openai_client(api_type)
    results: List[Dict] = []

    for i, p in enumerate(tqdm(prompts, desc=f"Generation ({api_type})")):
        messages = [
            {"role": "system", "content": "You are a helpful Lean 4 proving assistant. Please provide a complete Lean 4 proof for the given problem and return it inside a ```lean4 fenced block."},
            {"role": "user", "content": p},
        ]

        resp = client.chat.completions.create(
            model=model_name,
            messages=messages,
            n=n,
        )
        proofs = []
        for choice in resp.choices:
            full = choice.message.content or ""
            cleaned = extract_lean_block(full)
            proofs.append({"full_output": full, "cleaned_proof": cleaned})

        results.append({"idx": i, "prompt": p, "proofs": proofs})
        
    return results

# --------------------------
# Main
# --------------------------
def main():
    ap = argparse.ArgumentParser()
    # ap.add_argument("--dataset", type=str, default="updated_baseline_w_context/tao_analysis_baseline.jsonl")
    ap.add_argument("--dataset", type=str)
    # ap.add_argument("--outdir", type=str, default="updated_baseline_w_context")
    ap.add_argument("--outdir", type=str)
    ap.add_argument("--backend", type=str, choices=["vllm", "openai", "deepseek"], default="vllm",
                    help="vllm=local open-source (default), openai=GPT-5 API, deepseek=DeepSeek API")
    ap.add_argument("--model", type=str, default="deepseek-ai/DeepSeek-Prover-V2-7B",
                    help="For vllm: HF model id. For API: model name (e.g., 'gpt-5', 'deepseek-chat').")
    # ap.add_argument("--COT", type=bool, default=True, help="Whether to use COT or not.")
    ap.add_argument("--COT", type=str, default="True", choices=["True", "False"])
    ap.add_argument("--n", type=int, default=128, help="Number of samples per item")
    ap.add_argument("--max_new_tokens", type=int, default=2048)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--limit", type=int, default=0, help="Optional cap on #items (0 = all)")
    ap.add_argument("--tp_size", type=int, default=1, help="vLLM tensor_parallel_size")
    ap.add_argument("--gpu_mem_util", type=float, default=0.9)
    ap.add_argument("--max_model_len", type=int, default=8192)
    args = ap.parse_args()

    print(args.COT)
    # raise ValueError("Here!")
    
    problems = load_jsonl(args.dataset)
    print(len(problems))

    # raise ValueError("Here!")

    if args.limit > 0:
        problems = problems[:args.limit]

    prompts = [format_prompt(p, args.model, args.COT) for p in problems]

    if args.backend == "vllm":
        records = run_vllm_local(
            model_id=args.model,
            prompts=prompts,
            n=args.n,
            max_tokens=args.max_new_tokens,
            temperature=args.temperature,
            tensor_parallel_size=args.tp_size,
            gpu_mem_util=args.gpu_mem_util,
            max_model_len=args.max_model_len,
            outdir=args.outdir,
        )
    elif args.backend == "openai":
        records = run_openai_api(
            api_type="openai",
            model_name=args.model,
            prompts=prompts,
            n=args.n,
            max_tokens=args.max_new_tokens,
            temperature=args.temperature,
        )
    else:  # deepseek
        records = run_openai_api(
            api_type="deepseek",
            model_name=args.model,
            prompts=prompts,
            n=args.n,
            max_tokens=args.max_new_tokens,
            temperature=args.temperature,
        )


if __name__ == "__main__":
    main()
