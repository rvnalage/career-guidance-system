# TinyLlama Fine-Tuning Guide

## Overview

This guide walks you through fine-tuning TinyLlama (1.1B parameters) on your career guidance data. Optimized for CPU-only systems with QLoRA (parameter-efficient fine-tuning).

### What You'll Get
- A LoRA adapter (~50MB) trained on your 73 career guidance examples
- Improved responses for career-related questions
- Option to save as Ollama custom model or use directly in backend

---

## Prerequisites

### 1. Verify Python Environment
```powershell
cd career-guidance-system
.\.venv\Scripts\Activate.ps1
python --version  # Should be 3.13.x
```

### 2. Install Fine-tuning Dependencies
```powershell
pip install peft transformers datasets torch accelerate bitsandbytes
```

**Time:** 5-10 minutes (first time only)

---

## The Fine-Tuning Pipeline

### Step 1: Prepare Dataset (2 min)

Converts your 16 career guidance text files into 73 training examples:

```powershell
cd career-guidance-system

.\.venv\Scripts\python.exe ml-models/training/prepare_tinyllama_dataset.py `
  --input-dir "..\one_note_extract" `
  --output-file "ml-models/datasets/tinyllama_sft_generated.jsonl"
```

**Output:**
```
✅ Dataset prepared:
   Files processed: 16
   Training examples: 73
   Output: ml-models\datasets\tinyllama_sft_generated.jsonl
```

### Step 2: Fine-tune Model (1-2 hours on CPU)

Train the LoRA adapter on your career guidance data:

```powershell
.\.venv\Scripts\python.exe ml-models/training/train_tinyllama_cpu.py `
  --model "TinyLlama/TinyLlama-1.1B-Chat-v1.0" `
  --dataset "ml-models/datasets/tinyllama_sft_generated.jsonl" `
  --output-dir "ml-models/pretrained/tinyllama-career" `
  --epochs 1 `
  --batch-size 1 `
  --gradient-accumulation-steps 4
```

**What You'll See:**
- Initial model load: 1-2 minutes
- Tokenization: 1 minute
- Training starts with progress updates every 5 steps
- Checkpoints saved automatically
- Total: 45-90 minutes on typical CPU

**Parameters:**
| Param | Value | Reason |
|-------|-------|--------|
| `--epochs` | 1 | Single pass through 73 examples (fast) |
| `--batch-size` | 1 | CPUs can't handle larger batches |
| `--gradient-accumulation-steps` | 4 | Simulates batch size of 4 |
| `--max-length` | 512 | TinyLlama context window ~2000 tokens |

**Troubleshooting:**
| Issue | Solution |
|-------|----------|
| Out of memory | Reduce `--batch-size` to 1 (already done) |
| Still running slow | Normal on CPU; let it continue |
| Training interrupted? | Rerun same command; resumes from checkpoint |
| CUDA memory error | Remove any GPU drivers or restart terminal |

### Step 3: Evaluate Adapter (2 min)

Test the fine-tuned model on sample prompts:

```powershell
.\.venv\Scripts\python.exe ml-models/training/eval_tinyllama.py `
  --adapter-path "ml-models/pretrained/tinyllama-career"
```

**Sample Output:**
```
[1] User: I'm an MTech student interested in backend development. What should I focus on?