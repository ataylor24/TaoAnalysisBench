

CUDA_VISIBLE_DEVICES=2,3 python inference_baseline_TaoBenchMathlib.py \
    --dataset "/path/TaoBench_TaoBenchMathlib.jsonl" \
    --outdir "./your_file_path.jsonl" \
    --backend "vllm" \
    --model "deepseek-ai/DeepSeek-Prover-V2-7B" \
    --COT "False" \
    --n 128 \
    --max_new_tokens 8192 \
    --temperature 1.0 \
    --tp_size 2 \
    --max_model_len 8192

