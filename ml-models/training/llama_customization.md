# LLaMA Customization Guide (RAG + QLoRA)

## 1) Prepare Training Data

Use your extracted notes and generated conversations.

```bash
python ml-models/training/prepare_llama_dataset.py --input-dir one_note_extract --output-file ml-models/datasets/llama_sft_generated.jsonl
```

You can also start from:
- `ml-models/datasets/llama_sft_template.jsonl`

## 2) Install Training Dependencies

```bash
pip install datasets peft transformers accelerate bitsandbytes
```

Notes:
- GPU is strongly recommended for QLoRA.
- On CPU-only systems, training will be very slow.

## 3) Run QLoRA Fine-Tuning

```bash
python ml-models/training/train_llama_qlora.py --base-model meta-llama/Llama-3.1-8B-Instruct --dataset ml-models/datasets/llama_sft_generated.jsonl --output-dir ml-models/pretrained/llama-career-lora --epochs 1 --batch-size 1
```

## 4) Use Fine-Tuned Adapter (Suggested)

- Keep recommendation engine deterministic as source-of-truth.
- Use LLaMA for natural language explanation and guidance.
- Keep RAG enabled to ground outputs on project knowledge.

## 5) Evaluate Before Demo

Follow:
- `ml-models/evaluation/llama_eval_checklist.md`

Benchmark baseline vs fine-tuned model (Ollama):

```bash
python ml-models/evaluation/benchmark_llama.py --baseline-model llama3.1:8b --finetuned-model llama-career:latest
```

## 6) Backend Auto-Switch To Fine-Tuned Model

In `backend/.env`:

```env
LLM_ENABLED=true
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1:8b
LLM_FINETUNED_MODEL=llama-career:latest
```

If `LLM_FINETUNED_MODEL` is set, backend uses it automatically.

## 7) One-Click Pipeline (PowerShell)

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_llama_customization.ps1
```
