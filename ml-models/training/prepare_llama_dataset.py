from __future__ import annotations

import argparse
import json
from pathlib import Path

SYSTEM_PROMPT = (
    "You are a career guidance assistant for MTech students. "
    "Provide grounded, practical, and concise advice."
)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _chunk_text(text: str, chunk_size: int = 1200) -> list[str]:
    clean = " ".join(text.split())
    if not clean:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(clean):
        end = min(len(clean), start + chunk_size)
        chunks.append(clean[start:end])
        start = end
    return chunks


def _to_example(chunk: str) -> dict:
    user_prompt = (
        "Use the following notes and generate career guidance for an MTech student.\n\n"
        f"Notes:\n{chunk}\n"
    )
    assistant_text = (
        "Based on these notes, build a practical plan with skills, projects, and next actions. "
        "Include a short rationale and suggest one immediate next step."
    )
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": assistant_text},
        ]
    }


def build_dataset(input_dir: Path, output_file: Path) -> tuple[int, int]:
    files = sorted([p for p in input_dir.rglob("*.txt") if p.is_file()])
    examples: list[dict] = []

    for file_path in files:
        text = _read_text(file_path)
        for chunk in _chunk_text(text):
            examples.append(_to_example(chunk))

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8") as handle:
        for item in examples:
            handle.write(json.dumps(item, ensure_ascii=True) + "\n")

    return len(files), len(examples)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare SFT dataset for LLaMA fine-tuning")
    parser.add_argument("--input-dir", required=True, help="Directory containing source .txt files")
    parser.add_argument(
        "--output-file",
        default="ml-models/datasets/llama_sft_generated.jsonl",
        help="Output JSONL file",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_file = Path(args.output_file)

    if not input_dir.exists() or not input_dir.is_dir():
        raise SystemExit(f"Input directory not found: {input_dir}")

    file_count, example_count = build_dataset(input_dir, output_file)
    print(f"Prepared dataset from {file_count} files")
    print(f"Generated {example_count} examples at {output_file}")


if __name__ == "__main__":
    main()
