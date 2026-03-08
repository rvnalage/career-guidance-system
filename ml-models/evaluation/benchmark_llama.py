from __future__ import annotations

import argparse
import json
import time
from statistics import mean

import requests


PROMPTS = [
    "Give me an 8-week roadmap to become a data analyst.",
    "How should I prepare for machine learning interviews as an MTech student?",
    "My interests are AI and research, and my skills are Python and SQL. Suggest next steps.",
    "What career options fit high investigative and social psychometric traits?",
]


def run_generate(base_url: str, model: str, prompt: str, timeout: int) -> tuple[str, float]:
    url = f"{base_url.rstrip('/')}/api/generate"
    started = time.perf_counter()
    response = requests.post(
        url,
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=timeout,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.raise_for_status()
    text = str(response.json().get("response", "")).strip()
    return text, elapsed_ms


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare baseline and fine-tuned Ollama models")
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--baseline-model", required=True)
    parser.add_argument("--finetuned-model", required=True)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument(
        "--output",
        default="ml-models/evaluation/benchmark_results.json",
        help="Output JSON file",
    )
    args = parser.parse_args()

    rows: list[dict] = []
    baseline_latencies: list[float] = []
    finetuned_latencies: list[float] = []

    for prompt in PROMPTS:
        base_text, base_latency = run_generate(args.base_url, args.baseline_model, prompt, args.timeout)
        tuned_text, tuned_latency = run_generate(args.base_url, args.finetuned_model, prompt, args.timeout)

        baseline_latencies.append(base_latency)
        finetuned_latencies.append(tuned_latency)

        rows.append(
            {
                "prompt": prompt,
                "baseline": {
                    "model": args.baseline_model,
                    "latency_ms": round(base_latency, 2),
                    "response": base_text,
                },
                "finetuned": {
                    "model": args.finetuned_model,
                    "latency_ms": round(tuned_latency, 2),
                    "response": tuned_text,
                },
            }
        )

    report = {
        "summary": {
            "baseline_model": args.baseline_model,
            "finetuned_model": args.finetuned_model,
            "avg_baseline_latency_ms": round(mean(baseline_latencies), 2),
            "avg_finetuned_latency_ms": round(mean(finetuned_latencies), 2),
            "prompt_count": len(PROMPTS),
        },
        "results": rows,
    }

    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=True)

    print(f"Saved benchmark report to {args.output}")


if __name__ == "__main__":
    main()
