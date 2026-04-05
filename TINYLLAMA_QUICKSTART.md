# Quick Start: Fine-tune TinyLlama for Career Guidance

## One-Command Execution

Run the complete fine-tuning pipeline in one command:

```powershell
cd career-guidance-system

powershell -ExecutionPolicy Bypass -File scripts\run_tinyllama_finetuning.ps1 -Stage full
```

**Timeline:**
- Data Prep: 2 min (from `rag/knowledge/*.txt`)
- Training: 45-90 min on CPU
- Evaluation: 2 min
- **Total: ~1-2 hours**

---

## Running Specific Stages

### Stage 1: Prepare Dataset (2 min)
```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_tinyllama_finetuning.ps1 -Stage prepare
```
Output: 73 training examples (ml-models/datasets/tinyllama_sft_generated.jsonl)

### Stage 2: Train Model (45-90 min)
```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_tinyllama_finetuning.ps1 -Stage train
```
Output: LoRA adapter (ml-models/pretrained/tinyllama-career/)

### Stage 3: Evaluate (2 min)
```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_tinyllama_finetuning.ps1 -Stage evaluate
```
Tests model on sample career guidance prompts.

---

## Advanced Options

For better quality, increase training epochs:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_tinyllama_finetuning.ps1 `
  -Stage full -Epochs 3
```

**Tuning Parameters:**
- `-Epochs 3` → 3 passes through data (3x slower, better quality)
- `-MaxLength 256` → Smaller context (faster but less context)
- `-MaxLength 768` → Larger context (slower but more context)

---

## Integration Paths

### Path A: Direct HuggingFace in Backend (Quick)

Load fine-tuned adapter directly in `backend/app/services/llm_service.py`:

```python
# Use the adapter
from peft import PeftModel, AutoModelForCausalLM

def get_finetuned_model():
    base = AutoModelForCausalLM.from_pretrained("TinyLlama/TinyLlama-1.1B-Chat-v1.0")
    model = PeftModel.from_pretrained(base, "ml-models/pretrained/tinyllama-career")
    return model  # Use for inference
```

### Path B: Merge & Deploy to Ollama (Production)

```bash
# Merge adapter into base model
python -c "
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base = AutoModelForCausalLM.from_pretrained('TinyLlama/TinyLlama-1.1B-Chat-v1.0')
model = PeftModel.from_pretrained(base, 'ml-models/pretrained/tinyllama-career')
merged = model.merge_and_unload()
merged.save_pretrained('ml-models/pretrained/tinyllama-career-merged')
"

# Create Ollama custom model
ollama create tinyllama-career -f Modelfile
```

Then update `.env`:
```env
LLM_MODEL=tinyllama-career:latest
```

---

## What Happens

The fine-tuning process:

1. **Chunks** your 16 text files into 600-char segments
2. **Creates** 73 training examples (user prompts → ideal responses)
3. **Trains** TinyLlama with LoRA (parameter-efficient fine-tuning)
4. **Saves** ~50MB LoRA adapter that improves career guidance quality
5. **Evaluates** on 5 sample prompts to verify quality

The fine-tuned model becomes **specialized** for your specific career guidance domain while staying **compact** (~1.1B parameters).

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Module not found" | Run: `pip install peft transformers torch` |
| "Out of memory" | Reduce `--batch-size` to 1 (already default) |
| Training slow on CPU | Normal; NVIDIA GPU would be 10x faster |
| Training interrupted? | Rerun same command; resumes from checkpoint |
| Evaluation errors | Ensure training completed successfully |

---

## Next Steps After Training

✅ **Step 1:** Let training complete (watch for "Training complete!" message)  
✅ **Step 2:** Check evaluation output for quality  
✅ **Step 3:** Choose integration path (A for testing, B for production)  
✅ **Step 4:** Update backend config and restart  
✅ **Step 5:** Test in chat UI with career questions  

---

## Files Created

After successful training, you'll have:

```
ml-models/
└── datasets/
    └── tinyllama_sft_generated.jsonl      (73 training examples)
└── pretrained/
    └── tinyllama-career/                  (LoRA adapter ~50MB)
        ├── adapter_config.json
        ├── adapter_model.bin
        └── ...
```

These files are the **fine-tuned model adapter** ready for deployment.
