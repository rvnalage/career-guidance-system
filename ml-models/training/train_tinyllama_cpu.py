"""
TinyLlama fine-tuning script optimized for CPU training.
Uses QLoRA for memory efficiency + gradient accumulation.
Designed for MTech students with limited compute.
"""
from __future__ import annotations

import argparse
import inspect
import sys
from pathlib import Path


def _import_dependencies():
    """Lazy import dependencies with helpful error messages."""
    try:
        import torch
        from datasets import load_dataset
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            Trainer,
            TrainingArguments,
        )
        from transformers.trainer_utils import get_last_checkpoint
        return {
            "torch": torch,
            "load_dataset": load_dataset,
            "LoraConfig": LoraConfig,
            "get_peft_model": get_peft_model,
            "prepare_model_for_kbit_training": prepare_model_for_kbit_training,
            "AutoModelForCausalLM": AutoModelForCausalLM,
            "AutoTokenizer": AutoTokenizer,
            "Trainer": Trainer,
            "TrainingArguments": TrainingArguments,
            "get_last_checkpoint": get_last_checkpoint,
        }
    except ImportError as e:
        print("[ERROR] Missing dependencies. Install with:")
        print("   pip install datasets peft transformers torch")
        raise SystemExit(1) from e


def prepare_dataset(dataset_path: Path, tokenizer, max_length: int = 512):
    """Load and tokenize dataset."""
    print(f"Loading dataset from: {dataset_path}")
    
    # Load JSONL dataset
    from datasets import load_dataset
    dataset = load_dataset(
        "json",
        data_files=str(dataset_path),
        split="train"
    )
    
    print(f"   Total examples: {len(dataset)}")
    
    def tokenize_function(examples):
        """Convert messages to tokenized format."""
        texts = []
        for messages in examples["messages"]:
            # Build text from messages
            text = ""
            for msg in messages:
                role = msg.get("role", "").upper()
                content = msg.get("content", "")
                if role and content:
                    text += f"{role}: {content}\n"
            texts.append(text)
        
        # Tokenize
        return tokenizer(
            texts,
            truncation=True,
            max_length=max_length,
            padding="max_length",
            return_tensors="pt",
        )
    
    print("Tokenizing dataset (this may take a minute)...")
    tokenized = dataset.map(
        tokenize_function,
        batched=True,
        batch_size=64,
        remove_columns=dataset.column_names,
        desc="Tokenizing",
    )
    
    print(f"   Tokenized examples: {len(tokenized)}")
    return tokenized


def setup_lora(model, rank: int = 8, target_modules: list = None):
    """Configure LoRA for efficient fine-tuning."""
    if target_modules is None:
        target_modules = ["q_proj", "v_proj"]  # Common targets for TinyLlama
    
    lora_config = {
        "r": rank,
        "lora_alpha": 16,
        "target_modules": target_modules,
        "lora_dropout": 0.05,
        "bias": "none",
        "task_type": "CAUSAL_LM",
    }
    
    return lora_config


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fine-tune TinyLlama on CPU for career guidance"
    )
    parser.add_argument(
        "--model",
        default="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        help="Hugging Face model ID (default: TinyLlama 1.1B)"
    )
    parser.add_argument(
        "--dataset",
        required=True,
        help="Path to JSONL dataset"
    )
    parser.add_argument(
        "--output-dir",
        default="ml-models/pretrained/tinyllama-career",
        help="Output directory for fine-tuned adapter"
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=1,
        help="Number of training epochs"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="Training batch size (per device). Use 1 for CPU."
    )
    parser.add_argument(
        "--gradient-accumulation-steps",
        type=int,
        default=4,
        help="Gradient accumulation steps (simulates larger batches on CPU)"
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=2e-4,
        help="Learning rate"
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=512,
        help="Maximum sequence length (TinyLlama context ~2000 tokens)"
    )
    parser.add_argument(
        "--save-steps",
        type=int,
        default=5,
        help="Save checkpoint every N steps"
    )
    parser.add_argument(
        "--use-cpu",
        action="store_true",
        default=True,
        help="Force CPU training (default: True)"
    )
    parser.add_argument(
        "--mixed-precision",
        choices=["fp32", "fp16"],
        default="fp32",
        help="Precision: fp32 for CPU, fp16 for GPU"
    )
    
    args = parser.parse_args()
    
    # Import after arg parsing
    deps = _import_dependencies()
    torch = deps["torch"]
    load_dataset = deps["load_dataset"]
    LoraConfig = deps["LoraConfig"]
    get_peft_model = deps["get_peft_model"]
    prepare_model_for_kbit_training = deps["prepare_model_for_kbit_training"]
    AutoModelForCausalLM = deps["AutoModelForCausalLM"]
    AutoTokenizer = deps["AutoTokenizer"]
    Trainer = deps["Trainer"]
    TrainingArguments = deps["TrainingArguments"]
    get_last_checkpoint = deps["get_last_checkpoint"]
    
    # Validate dataset
    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"[ERROR] Dataset not found: {dataset_path}")
        raise SystemExit(1)
    
    print("\n" + "="*60)
    print("TinyLlama CPU Fine-tuning")
    print("="*60)
    print(f"Model: {args.model}")
    print(f"Dataset: {dataset_path}")
    print(f"Output: {args.output_dir}")
    print(f"Epochs: {args.epochs} | Batch size: {args.batch_size} | Grad accumulation: {args.gradient_accumulation_steps}")
    print(f"Checkpoint every: {args.save_steps} steps")
    print("Device: CPU (training will be slow but feasible)")
    print("="*60 + "\n")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    last_checkpoint = get_last_checkpoint(str(output_dir))
    if last_checkpoint:
        print(f"Resuming from checkpoint: {last_checkpoint}")
    else:
        print("No checkpoint found. Starting a fresh training run.")
    
    # Load tokenizer and model
    print("Loading tokenizer and model...")
    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    # For CPU, use standard loading (no 4-bit quantization)
    print("   Loading model (this may take a minute)...")
    try:
        from_pretrained_params = inspect.signature(AutoModelForCausalLM.from_pretrained).parameters
        model_load_kwargs = {"low_cpu_mem_usage": True}
        if "dtype" in from_pretrained_params:
            model_load_kwargs["dtype"] = torch.float32
        else:
            model_load_kwargs["torch_dtype"] = torch.float32
        if "device_map" in from_pretrained_params:
            model_load_kwargs["device_map"] = "cpu"

        model = AutoModelForCausalLM.from_pretrained(args.model, **model_load_kwargs)
    except Exception as e:
        print(f"[ERROR] Failed to load model: {e}")
        raise SystemExit(1) from e
    
    # Prepare dataset
    tokenized_dataset = prepare_dataset(
        dataset_path,
        tokenizer,
        max_length=args.max_length
    )
    
    # Configure LoRA
    print("\nConfiguring LoRA...")
    lora_config_dict = setup_lora(model, rank=8)
    lora_config = LoraConfig(**lora_config_dict)
    
    # Prepare model for LoRA
    model = get_peft_model(model, lora_config)
    
    print(f"   LoRA rank: 8")
    print(f"   Trainable parameters: {sum(p.numel() for p in model.parameters() if p.requires_grad):,}")
    print(f"   Total parameters: {sum(p.numel() for p in model.parameters()):,}")
    
    # Training arguments optimized for CPU
    print("\nSetting up training...")
    training_args = TrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        learning_rate=args.learning_rate,
        lr_scheduler_type="linear",
        warmup_steps=max(10, len(tokenized_dataset) // 100),
        weight_decay=0.01,
        logging_steps=5,
        save_steps=args.save_steps,
        eval_strategy="no",  # Skip eval on CPU to save time
        save_strategy="steps",
        save_total_limit=2,
        bf16=False,  # Don't use bfloat16 on CPU
        fp16=False,  # Don't use fp16 on CPU without GPU
        dataloader_pin_memory=False,
        dataloader_drop_last=False,
        logging_first_step=True,
        logging_dir=str(output_dir / "logs"),
        report_to=[],  # Disable external reporting integrations
        seed=42,
    )
    
    # Create trainer
    trainer_kwargs = {
        "model": model,
        "args": training_args,
        "train_dataset": tokenized_dataset,
    }
    trainer_params = inspect.signature(Trainer.__init__).parameters
    if "tokenizer" in trainer_params:
        trainer_kwargs["tokenizer"] = tokenizer
    elif "processing_class" in trainer_params:
        trainer_kwargs["processing_class"] = tokenizer

    trainer = Trainer(**trainer_kwargs)
    
    # Start training
    print("\n" + "="*60)
    print("Starting training (CPU mode - this will be slow)")
    print("="*60 + "\n")
    print("Estimated time: 30-60 minutes per epoch on CPU")
    print("   (Depends on CPU cores and dataset size)\n")
    
    try:
        trainer.train(resume_from_checkpoint=last_checkpoint)
    except KeyboardInterrupt:
        print("\n\n[WARN] Training interrupted. Saving checkpoint...")
        trainer.save_model(args.output_dir)
    except Exception as e:
        print(f"\n[ERROR] Training failed: {e}")
        raise SystemExit(1) from e
    
    # Save final model
    print("\nTraining complete!")
    print(f"Saving model to: {args.output_dir}")
    trainer.save_model(args.output_dir)
    
    # Print next steps
    print("\n" + "="*60)
    print("Next steps:")
    print("="*60)
    print(f"1. Review trained adapter at: {args.output_dir}")
    print("2. Run evaluation: python ml-models/evaluation/eval_tinyllama.py \\")
    print(f"   --adapter-path {args.output_dir}")
    print("3. Export for Ollama integration")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
