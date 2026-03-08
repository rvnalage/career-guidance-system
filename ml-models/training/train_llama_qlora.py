from __future__ import annotations

import argparse
from pathlib import Path


def _import_dependencies() -> tuple:
    try:
        import torch
        from datasets import load_dataset
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, Trainer, TrainingArguments
    except Exception as exc:
        raise SystemExit(
            "Missing dependencies. Install: pip install datasets peft transformers accelerate bitsandbytes"
        ) from exc

    return (
        torch,
        load_dataset,
        LoraConfig,
        get_peft_model,
        prepare_model_for_kbit_training,
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        Trainer,
        TrainingArguments,
    )


def _format_chat_example(example: dict) -> str:
    messages = example.get("messages", [])
    lines: list[str] = []
    for msg in messages:
        role = str(msg.get("role", "user")).strip().upper()
        content = str(msg.get("content", "")).strip()
        lines.append(f"{role}: {content}")
    lines.append("ASSISTANT:")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="QLoRA fine-tuning for LLaMA on custom career guidance data")
    parser.add_argument("--base-model", default="meta-llama/Llama-3.1-8B-Instruct")
    parser.add_argument("--dataset", default="ml-models/datasets/llama_sft_generated.jsonl")
    parser.add_argument("--output-dir", default="ml-models/pretrained/llama-career-lora")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--max-length", type=int, default=1024)
    args = parser.parse_args()

    (
        torch,
        load_dataset,
        LoraConfig,
        get_peft_model,
        prepare_model_for_kbit_training,
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        Trainer,
        TrainingArguments,
    ) = _import_dependencies()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        raise SystemExit(f"Dataset not found: {dataset_path}")

    tokenizer = AutoTokenizer.from_pretrained(args.base_model, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    use_4bit = torch.cuda.is_available()
    quant_config = None
    if use_4bit:
        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
        )

    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        quantization_config=quant_config,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        device_map="auto" if torch.cuda.is_available() else None,
    )

    if use_4bit:
        model = prepare_model_for_kbit_training(model)

    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, lora_config)

    raw_dataset = load_dataset("json", data_files=str(dataset_path), split="train")

    def preprocess(example: dict) -> dict:
        text = _format_chat_example(example)
        tokenized = tokenizer(
            text,
            truncation=True,
            max_length=args.max_length,
            padding="max_length",
        )
        tokenized["labels"] = tokenized["input_ids"].copy()
        return tokenized

    tokenized_dataset = raw_dataset.map(preprocess, remove_columns=raw_dataset.column_names)

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=8,
        learning_rate=args.learning_rate,
        logging_steps=10,
        save_steps=100,
        save_total_limit=2,
        fp16=torch.cuda.is_available(),
        bf16=False,
        optim="paged_adamw_8bit" if use_4bit else "adamw_torch",
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        tokenizer=tokenizer,
    )

    trainer.train()
    model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    print(f"Saved LoRA adapter to: {args.output_dir}")


if __name__ == "__main__":
    main()
