# LLaMA Customization Evaluation Checklist

## Dataset Quality

- Verify no PII or sensitive personal data in training records.
- Remove contradictory or low-quality answers.
- Keep response style consistent with project goals (practical, concise, grounded).
- Ensure class/topic balance across career roles and question types.

## Offline Validation

- Exactness: check whether recommendations align with known role requirements.
- Grounding: verify answer references retrieved context when available.
- Hallucination rate: track unsupported claims per 100 prompts.
- Helpfulness: rate actionability of responses on a 1-5 scale.
- Safety: ensure no harmful, discriminatory, or unrealistic advice.

## Online Validation (App)

- Test with `RAG_ENABLED=true` and `LLM_ENABLED=true`.
- Confirm chat responses return `rag_citations` for domain-heavy questions.
- Compare baseline deterministic response vs LLaMA-enhanced response.
- Verify fallback works when LLM is unavailable.

## Metrics Table Template

| Metric | Baseline | LLaMA + RAG | Target |
|---|---:|---:|---:|
| Hallucination rate (%) |  |  | <= 5 |
| Helpfulness score (1-5) |  |  | >= 4 |
| Grounded response ratio (%) |  |  | >= 90 |
| Avg response latency (ms) |  |  | <= 2500 |

## Release Gate

- All core tests pass.
- Hallucination rate under threshold.
- Grounded response ratio meets target.
- Demo prompts consistently produce actionable plans.
