

CUDA_VISIBLE_DEVICES=6,7 python inference_baseline_TaoBench.py \
    --dataset "/path/TaoBench_TaoBenchMathlib.jsonl" \
    --outdir "./your_file_path.jsonl" \
    --backend "vllm" \
    --model "AI-MO/Kimina-Prover-Distill-8B" \
    --COT "True" \
    --n 128 \
    --max_new_tokens 8192 \
    --temperature 1.0 \
    --tp_size 2 \
    --max_model_len 8192

