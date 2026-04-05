"""
Evaluate fine-tuned TinyLlama model on sample prompts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate fine-tuned TinyLlama model")
    parser.add_argument(
        "--adapter-path",
        required=True,
        help="Path to LoRA adapter directory"
    )
    parser.add_argument(
        "--base-model",
        default="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        help="Base model ID"
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=150,
        help="Max tokens to generate"
    )
    
    args = parser.parse_args()
    
    # Import dependencies
    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        raise SystemExit(1) from e
    
    adapter_path = Path(args.adapter_path)
    if not adapter_path.exists():
        print(f"❌ Adapter path not found: {adapter_path}")
        raise SystemExit(1)
    
    print("\n" + "="*60)
    print("TinyLlama Fine-tuned Model Evaluation")
    print("="*60)
    print(f"Base model: {args.base_model}")
    print(f"Adapter: {adapter_path}")
    print("="*60 + "\n")
    
    # Load base model
    print("🔄 Loading base model and adapter...")
    try:
        base_model = AutoModelForCausalLM.from_pretrained(
            args.base_model,
            torch_dtype=torch.float32,
            device_map="cpu"
        )
        
        tokenizer = AutoTokenizer.from_pretrained(args.base_model)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        
        # Load LoRA adapter
        model = PeftModel.from_pretrained(base_model, adapter_path)
        model.eval()
        
        print("✅ Model loaded successfully\n")
    
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        raise SystemExit(1) from e
    
    # Sample evaluation prompts
    test_prompts = [
        "I'm an MTech student interested in backend development. What should I focus on?",
        "How should I prepare for technical interviews?",
        "What's the best way to build a portfolio for a career switch?",
        "How do I decide between higher studies and getting a job?",
        "What are the key skills for a machine learning engineer?",
    ]
    
    print("🧪 Sample Evaluations")
    print("-" * 60)
    
    with torch.no_grad():
        for i, prompt in enumerate(test_prompts, 1):
            print(f"\n[{i}] User: {prompt}")
            
            # Tokenize and generate
            inputs = tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=512
            )
            
            outputs = model.generate(
                **inputs,
                max_new_tokens=args.max_tokens,
                temperature=0.7,
                top_p=0.9,
                do_sample=True,
                eos_token_id=tokenizer.eos_token_id,
                pad_token_id=tokenizer.pad_token_id,
            )
            
            response = tokenizer.decode(outputs[0], skip_special_tokens=True)
            # Remove the prompt from the response
            response = response[len(prompt):].strip()
            
            print(f"\nAssistant: {response[:250]}...")
            print("-" * 60)
    
    print("\n✅ Evaluation complete!")


if __name__ == "__main__":
    main()
