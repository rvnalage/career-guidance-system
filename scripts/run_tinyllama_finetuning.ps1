param(
    [string]$Stage = "full",
    [int]$Epochs = 1,
    [int]$BatchSize = 1,
    [int]$GradAccum = 4,
    [int]$SaveSteps = 5,
    [int]$MaxLength = 512,
    [string]$BaseModel = "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    [switch]$SkipPrepare = $false,
    [switch]$SkipTrain = $false,
    [switch]$SkipEval = $false
)

# Stage options: full | prepare | train | evaluate

$ErrorActionPreference = "Stop"

# Colors for output
$Green = "Green"
$Yellow = "Yellow"
$Red = "Red"
$Cyan = "Cyan"

function Write-Status {
    param([string]$Message, [string]$Color = $Cyan)
    Write-Host $Message -ForegroundColor $Color
}

function Write-Step {
    param([string]$Message)
    Write-Host "`n" -NoNewline
    Write-Status "> $Message" -Color $Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Status "[OK] $Message" -Color $Green
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Status "[ERROR] $Message" -Color $Red
}

# Get workspace root
$WorkspaceRoot = Split-Path $PSScriptRoot

Write-Status @"
=============================
 TinyLlama Fine-Tuning
 Orchestrator
=============================
"@ -Color $Cyan

Write-Status "Workspace: $WorkspaceRoot`n"

# Verify environment
Write-Step "Verifying Python environment..."

$PythonExe = "$WorkspaceRoot\.venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Error-Custom "Python environment not found at: $PythonExe"
    exit 1
}

$PythonVersion = & $PythonExe --version 2>&1
Write-Success "Python environment ready: $PythonVersion"

# Check for required packages
Write-Step "Checking fine-tuning dependencies..."
$RequiredPackages = @("torch", "transformers", "peft", "datasets", "accelerate")
$MissingPackages = @()

foreach ($pkg in $RequiredPackages) {
    $check = & $PythonExe -c "import $pkg" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Status "  [OK] $pkg" -Color $Green
    }
    else {
        $MissingPackages += $pkg
    }
}

if ($MissingPackages.Count -gt 0) {
    Write-Error-Custom "Missing packages: $($MissingPackages -join ', ')"
    Write-Status "`nInstall with:"
    Write-Status "  pip install $($MissingPackages -join ' ')" -Color $Yellow
    exit 1
}

Write-Success "`nAll dependencies available`n"

# ============================================
# STAGE 1: PREPARE DATASET
# ============================================
if ($Stage -eq "prepare" -or ($Stage -eq "full" -and -not $SkipPrepare)) {
    Write-Step "Stage 1/3: Preparing dataset..."
    
    $DatasetScript = "$WorkspaceRoot\ml-models\training\prepare_tinyllama_dataset.py"
    $InputDir = "$WorkspaceRoot\rag\knowledge"
    $OutputFile = "$WorkspaceRoot\ml-models\datasets\tinyllama_sft_generated.jsonl"
    
    if (-not (Test-Path $InputDir)) {
        Write-Error-Custom "Input directory not found: $InputDir"
        exit 1
    }
    
    Write-Status "  Input:  $InputDir"
    Write-Status "  Output: $OutputFile`n"
    
    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $PythonExe $DatasetScript --input-dir $InputDir --output-file $OutputFile
    $ErrorActionPreference = $previousErrorAction
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Dataset preparation complete"
    }
    else {
        Write-Error-Custom "Dataset preparation failed"
        exit 1
    }
}

# ============================================
# STAGE 2: TRAIN MODEL
# ============================================
if ($Stage -eq "train" -or ($Stage -eq "full" -and -not $SkipTrain)) {
    Write-Step "Stage 2/3: Training fine-tuned model..."
    
    $TrainScript = "$WorkspaceRoot\ml-models\training\train_tinyllama_cpu.py"
    $DatasetFile = "$WorkspaceRoot\ml-models\datasets\tinyllama_sft_generated.jsonl"
    $OutputDir = "$WorkspaceRoot\ml-models\pretrained\tinyllama-career"
    
    if (-not (Test-Path $DatasetFile)) {
        Write-Error-Custom "Dataset file not found. Please run 'prepare' stage first."
        exit 1
    }
    
    Write-Status "  Base model:    $BaseModel"
    Write-Status "  Dataset:       $DatasetFile"
    Write-Status "  Output:        $OutputDir"
    Write-Status "  Configuration:"
    Write-Status "    Epochs:              $Epochs"
    Write-Status "    Batch size:          $BatchSize"
    Write-Status "    Grad accumulation:   $GradAccum"
    Write-Status "    Save steps:          $SaveSteps"
    Write-Status "    Max length:          $MaxLength`n"
    Write-Status "Estimated time: 45-90 minutes on CPU`n" -Color $Yellow
    
    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $PythonExe $TrainScript `
        --model $BaseModel `
        --dataset $DatasetFile `
        --output-dir $OutputDir `
        --epochs $Epochs `
        --batch-size $BatchSize `
        --gradient-accumulation-steps $GradAccum `
        --save-steps $SaveSteps `
        --max-length $MaxLength
    $ErrorActionPreference = $previousErrorAction
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Model training complete"
    }
    else {
        Write-Error-Custom "Model training failed"
        exit 1
    }
}

# ============================================
# STAGE 3: EVALUATE MODEL
# ============================================
if ($Stage -eq "evaluate" -or ($Stage -eq "full" -and -not $SkipEval)) {
    Write-Step "Stage 3/3: Evaluating fine-tuned model..."
    
    $EvalScript = "$WorkspaceRoot\ml-models\training\eval_tinyllama.py"
    $AdapterPath = "$WorkspaceRoot\ml-models\pretrained\tinyllama-career"
    
    if (-not (Test-Path $AdapterPath)) {
        Write-Error-Custom "Adapter directory not found at: $AdapterPath"
        Write-Status "Please run the 'train' stage first."
        exit 1
    }
    
    Write-Status "  Adapter: $AdapterPath`n"
    
    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $PythonExe $EvalScript `
        --adapter-path $AdapterPath `
        --base-model $BaseModel
    $ErrorActionPreference = $previousErrorAction
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Model evaluation complete"
    }
    else {
        Write-Error-Custom "Model evaluation failed"
        exit 1
    }
}

# ============================================
# FINAL SUMMARY
# ============================================
Write-Status @"

=============================================
 Fine-Tuning Pipeline Complete
=============================================

Output Directory:
   ml-models/pretrained/tinyllama-career

Next Steps:
   1. Review the evaluation output above
   
   2. (Optional) Test in your application:
      - Update backend to use fine-tuned model
      - Restart Ollama with custom modelfile
      
   3. (Optional) Fine-tune further:
      - Increase --epochs to 3-5 for better results
      - Add more training data

Documentation:
   ml-models/training/TINYLLAMA_FINETUNING_GUIDE.md

"@ -Color $Green

exit 0
