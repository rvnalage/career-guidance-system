param(
    [string]$InputDir = "one_note_extract",
    [string]$OutputDataset = "ml-models/datasets/llama_sft_generated.jsonl",
    [string]$BaseModel = "meta-llama/Llama-3.1-8B-Instruct",
    [string]$OutputAdapter = "ml-models/pretrained/llama-career-lora",
    [int]$Epochs = 1,
    [int]$BatchSize = 1,
    [switch]$SkipInstall,
    [switch]$SkipTraining
)

$ErrorActionPreference = "Stop"

Write-Host "[1/3] Preparing dataset..."
python ml-models/training/prepare_llama_dataset.py --input-dir $InputDir --output-file $OutputDataset

if (-not $SkipInstall) {
    Write-Host "[2/3] Installing training dependencies..."
    python -m pip install datasets peft transformers accelerate bitsandbytes
}
else {
    Write-Host "[2/3] Skipped dependency installation"
}

if (-not $SkipTraining) {
    Write-Host "[3/3] Starting QLoRA training..."
    python ml-models/training/train_llama_qlora.py --base-model $BaseModel --dataset $OutputDataset --output-dir $OutputAdapter --epochs $Epochs --batch-size $BatchSize
}
else {
    Write-Host "[3/3] Skipped training"
}

Write-Host "Completed. Next: review ml-models/evaluation/llama_eval_checklist.md"
