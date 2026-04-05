"""
Prepare SFT dataset for TinyLlama fine-tuning on career guidance data.
Uses text files from rag/knowledge/ (consolidated career guidance knowledge base).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

# Simple, focused system prompt for TinyLlama
SYSTEM_PROMPT = (
    "You are a helpful career guidance assistant for MTech students. "
    "Provide practical, actionable advice based on the context provided."
)


def _read_text(path: Path) -> str:
    """Read text file with error handling."""
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def _chunk_text(text: str, chunk_size: int = 600) -> list[str]:
    """
    Split text into chunks.
    TinyLlama has smaller context window (~2048 tokens), so use smaller chunks.
    """
    if not text:
        return []
    
    # Clean whitespace
    clean = " ".join(text.split())
    if not clean:
        return []
    
    chunks: list[str] = []
    words = clean.split()
    current_chunk = []
    current_size = 0
    
    for word in words:
        current_chunk.append(word)
        current_size += len(word) + 1
        
        if current_size >= chunk_size:
            chunks.append(" ".join(current_chunk))
            current_chunk = []
            current_size = 0
    
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    
    return chunks


def _to_training_example(chunk: str, source_file: str) -> dict:
    """
    Convert a text chunk into a training example for TinyLlama.
    Format: user prompt → assistant response with practical guidance.
    """
    # Create focused prompt based on content type
    if any(word in source_file.lower() for word in ["path", "roadmap"]):
        user_prompt = (
            f"Based on this career development content, provide a practical learning roadmap:\n\n{chunk}\n\n"
            "What are the key steps?"
        )
        assistant_response = (
            "Here's a practical roadmap: Start with fundamentals, build one project, "
            "then move to advanced topics. Focus on hands-on practice over theory."
        )
    elif "interview" in source_file.lower():
        user_prompt = (
            f"Based on this interview guidance:\n\n{chunk}\n\n"
            "What are the most important preparation strategies?"
        )
        assistant_response = (
            "Key strategies: practice with real problems, explain your thinking clearly, "
            "ask clarifying questions, and prepare examples from your projects."
        )
    elif "resume" in source_file.lower() or "portfolio" in source_file.lower():
        user_prompt = (
            f"Based on this portfolio/resume advice:\n\n{chunk}\n\n"
            "How should I structure my profile?"
        )
        assistant_response = (
            "Structure with impact: quantify achievements, link projects, explain the business value, "
            "and keep it concise. Show results, not just tools used."
        )
    else:
        user_prompt = (
            f"Based on this career guidance:\n\n{chunk}\n\n"
            "What's my best next action?"
        )
        assistant_response = (
            "Identify the gap in your profile first, then focus single-mindedly on closing it. "
            "Build projects that demonstrate that skill."
        )
    
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": assistant_response},
        ]
    }


def build_dataset(input_dir: Path, output_file: Path, max_files: int = None) -> tuple[int, int]:
    """
    Build training dataset from text files.
    
    Args:
        input_dir: Directory containing .txt files
        output_file: Output JSONL file path
        max_files: Optionally limit number of files (useful for quick testing)
    
    Returns:
        (num_files_processed, num_examples_generated)
    """
    files = sorted([p for p in input_dir.rglob("*.txt") if p.is_file()])
    
    if max_files:
        files = files[:max_files]
    
    examples: list[dict] = []
    processed_files = 0
    
    for file_path in files:
        try:
            text = _read_text(file_path)
            if not text:
                continue
            
            # Create chunks and training examples
            chunks = _chunk_text(text, chunk_size=600)
            for chunk in chunks:
                if len(chunk) > 50:  # Skip very short chunks
                    example = _to_training_example(chunk, file_path.name)
                    examples.append(example)
            
            processed_files += 1
            print(f"  ✓ {file_path.name}: {len(chunks)} chunks")
        
        except Exception as e:
            print(f"  ✗ {file_path.name}: {e}")
            continue
    
    # Write dataset
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8") as f:
        for item in examples:
            f.write(json.dumps(item, ensure_ascii=True) + "\n")
    
    return processed_files, len(examples)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare career guidance dataset for TinyLlama fine-tuning"
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing source .txt files (e.g., rag/knowledge/)"
    )
    parser.add_argument(
        "--output-file",
        default="ml-models/datasets/tinyllama_sft_generated.jsonl",
        help="Output JSONL file path",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Limit to first N files (for quick testing)"
    )
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    output_file = Path(args.output_file)
    
    if not input_dir.exists() or not input_dir.is_dir():
        raise SystemExit(f"Input directory not found: {input_dir}")
    
    print(f"📊 Preparing TinyLlama dataset from: {input_dir}")
    if args.max_files:
        print(f"   (Limited to {args.max_files} files for testing)")
    
    file_count, example_count = build_dataset(input_dir, output_file, args.max_files)
    
    print(f"\n✅ Dataset prepared:")
    print(f"   Files processed: {file_count}")
    print(f"   Training examples: {example_count}")
    print(f"   Output: {output_file}")


if __name__ == "__main__":
    main()
