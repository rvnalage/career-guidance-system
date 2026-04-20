# RAG + LLM Integration: Code-Level Explanation

## Overview

This document explains how the career guidance system integrates RAG (Retrieval-Augmented Generation) with the LLM to provide grounded, accurate responses based on your career knowledge base.

For ingestion runbooks, chunk-quality controls, and troubleshooting, also see: `docs/rag-ingestion-operations.md`.

**Key Principle:** The LLM doesn't generate from its training data alone—it receives your specific career guidance knowledge as part of the prompt, ensuring responses are grounded in your curated content.

---

## Architecture

```
User Message
    ↓
[Agent] (Deterministic recommendation)
    ↓
[RAG] (Retrieve context from rag/knowledge/)
    ↓
[Build Prompt] (Combine agent + RAG context)
    ↓
[LLM] (TinyLlama or OpenAI)
    ↓
Final Response + Citations
```

---

## Code Flow: Step-by-Step

### Step 1: User Sends Message

**File:** `backend/app/api/routes/chat.py` → `send_message()`

```python
@router.post("/message", response_model=ChatResponse)
async def send_message(payload: ChatRequest) -> ChatResponse:
    """Process user message through agent → RAG → LLM pipeline."""
    
    user_message = payload.message  # e.g., "How do I prepare for interviews?"
    
    # Step 1a: Get agent response (deterministic)
    intent, reply, next_step, confidence, keyword_matches = get_agent_response_with_confidence(
        user_message,
        resolved_context,
    )
    # Output: intent="interview_prep", reply="Practice coding problems"
    
    # Step 1b: RETRIEVE FROM RAG ← Core integration point
    rag_context = build_rag_context(user_message)
    # Output: "- Interview Prep: Practice daily...\n- Portfolio Tips: Quantify..."
    
    rag_citations = get_rag_citations(user_message)
    # Output: [{"title": "Interview Prep", "source": "interview_preparation.txt"}]
    
    # Step 1c: Pass everything to LLM
    enhanced_reply = generate_llm_reply(
        message=user_message,
        intent=intent,
        base_reply=reply,
        next_step=next_step,
        rag_context=rag_context,  # ← RAG CONTEXT PASSED HERE
        **kwargs
    )
    
    # If LLM returns None (disabled or no RAG), use agent reply + context
    final_reply = enhanced_reply or augmented_reply
```

**Key Point:** The RAG context is retrieved *before* calling the LLM, then injected into the prompt.

---

### Step 2: RAG Retrieval

**File:** `backend/app/services/rag_service.py`

#### `build_rag_context()` - Format context as bullet list

```python
def build_rag_context(query: str) -> str:
    """Convert retrieved chunks into a bullet-list context string."""
    
    chunks = retrieve_relevant_chunks(query)
    # chunks = [
    #   KnowledgeChunk(
    #     title="Interview Preparation",
    #     text="Practice coding problems. Tell STAR stories...",
    #     source="interview_preparation.txt"
    #   ),
    #   KnowledgeChunk(
    #     title="Portfolio Guidelines",
    #     text="Quantify achievements. Link projects...",
    #     source="resume_portfolio_guidelines.txt"
    #   )
    # ]
    
    if not chunks:
        return ""
    
    # Format as bullet list for LLM readability
    lines = [f"- {chunk.title}: {chunk.text}" for chunk in chunks]
    return "\n".join(lines)

# Returns:
# "- Interview Preparation: Practice coding problems...
#  - Portfolio Guidelines: Quantify achievements..."
```

#### `retrieve_relevant_chunks()` - Retrieve from knowledge base

```python
def retrieve_relevant_chunks(query: str, top_k: int = None) -> list[KnowledgeChunk]:
    """Retrieve top-K relevant chunks using vector search + reranking."""
    
    if not settings.rag_enabled:
        return []
    
    _ensure_vector_index()  # Build vector index on first call
    
    # Rewrite query for better retrieval
    rewritten_query = rewrite_query(query)
    # "How do I prepare for interviews?" 
    # → "interview preparation coding practice STAR storytelling"
    
    # Retrieve from rag/knowledge/ using vector search
    limit = top_k if top_k is not None else settings.rag_top_k  # Default: 4
    
    results = RETRIEVER.retrieve(
        query=rewritten_query,
        top_k=max(1, limit),
        fallback_chunks=_active_corpus(),  # Built-in career paths + extras
        metadata_filters=resolved_filters,
        candidate_pool_size=max(limit, settings.rag_candidate_pool_size),  # 20
    )
    
    return results  # Top-k most relevant chunks from rag/knowledge/
```

#### `Retriever.retrieve()` - Multi-stage ranking

**File:** `backend/app/rag/retriever.py`

```python
class Retriever:
    def retrieve(self, query: str, top_k: int, ...) -> list[KnowledgeChunk]:
        """Multi-stage retrieval: vector search → lexical reranking → metadata scoring."""
        
        query_tokens = _tokenize(query)
        # {"interview", "preparation", "coding", "practice"}
        
        # Stage 1: Vector search (TF-IDF similarity)
        candidates = self.store.search(query=query, top_k=20)
        # Returns (vector_score, chunk) pairs from all docs
        
        # Stage 2: Rerank candidates with combined scoring
        reranked = []
        for vector_score, chunk in candidates:
            chunk_tokens = _tokenize(f"{chunk.title} {chunk.text}")
            
            # Component 1: Vector similarity (TF-IDF)
            # e.g., 0.85 (how well content matches query)
            
            # Component 2: Lexical overlap bonus
            lexical_overlap = len(query_tokens.intersection(chunk_tokens)) * 0.1
            # If chunk shares "interview", "preparation" → boost score
            
            # Component 3: Metadata matching
            metadata_score = _metadata_score(query_tokens, chunk)
            # If chunk.metadata["topic"] == "interview" → bonus
            
            # Combined score
            total_score = vector_score + lexical_overlap + metadata_score
            reranked.append((total_score, chunk))
        
        # Stage 3: Sort and return top-K
        reranked.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in reranked[:top_k]]
```

**Retrieval Sources:**
- Primary: `rag/knowledge/*.txt` (16 career guidance files)
- Fallback: `BASE_CORPUS` (built-in career paths from `app.utils.constants`)

---

### Step 3: Build LLM Prompt

**File:** `backend/app/services/llm_service.py` → `_build_prompt()`

```python
def _build_prompt(
    message: str,
    intent: str,
    base_reply: str,  # Agent's recommendation
    next_step: str,
    rag_context: str,  # ← RAG RETRIEVED CONTEXT
    intent_confidence: float,
    keyword_matches: list[str],
    user_profile_summary: str,
) -> str:
    """Build structured prompt that grounds LLM in retrieved context."""
    
    rag_section = rag_context.strip() or "No retrieved context."
    intent_guidance = INTENT_PROMPT_GUIDANCE.get(intent, "Keep response concise.")
    
    return (
        f"System: You are a concise career guidance assistant for MTech students.\n"
        f"Use only the retrieved context and base guidance as source-of-truth.\n"
        f"Do not invent facts or make up information.\n"
        f"Reply in at most 8 short sentences.\n"
        
        # Context about what the LLM should do for this intent
        f"Intent-specific guidance: {intent_guidance}\n"
        f"(For interview_prep: Prioritize role-specific practice + STAR behavioral stories.)\n"
        
        # Everything we know about the user
        f"User message: {message}\n"
        f"Detected intent: {intent} (confidence: {intent_confidence:.2f})\n"
        f"Matched keywords: {', '.join(keyword_matches) if keyword_matches else 'none'}\n"
        f"User profile: {user_profile_summary}\n"
        
        # ← THIS IS THE KEY PART: RAG CONTEXT
        f"Retrieved context from your knowledge base:\n{rag_section}\n"
        # Example output:
        # "- Interview Preparation: Practice daily, tell STAR stories...
        #  - Portfolio Guidelines: Quantify achievements..."
        
        # Agent's deterministic recommendation
        f"Base guidance: {base_reply}\n"
        f"Next step: {next_step}\n"
        
        # Final instruction
        f"Return only the final reply text."
    )

# Example prompt sent to LLM:
# ---
# System: You are a concise career guidance assistant...
# Intent-specific guidance: Prioritize role-specific practice...
# User message: How do I prepare for interviews?
# Detected intent: interview_prep (confidence: 0.92)
#
# Retrieved context from your knowledge base:
# - Interview Preparation: Practice problems daily. 
#   Tell STAR stories with metrics from your projects...
# - Resume Portfolio Guidelines: Quantify achievements...
#
# Base guidance: Practice coding problems systematically
# Next step: Build and document one project
#
# Return only the final reply text.
# ---
```

**Key Principle:** The prompt is *structured* to guide the LLM:
- System instructions emphasis: "Use only retrieved context"
- Retrieved context is clearly labeled and comes first
- Base agent response is included for secondary reference
- Sentence limit enforced (prevents rambling)

---

### Step 4: LLM Call & Response

**File:** `backend/app/services/llm_service.py` → `generate_llm_reply()`

```python
def generate_llm_reply(
    *,
    message: str,
    intent: str,
    base_reply: str,
    next_step: str,
    rag_context: str = "",
    **kwargs
) -> Optional[str]:
    """Return LLM-refined reply when conditions permit."""
    
    runtime = _resolve_runtime_config()
    
    # Check 1: Is LLM enabled?
    if not bool(runtime.get("enabled", False)):
        return None  # Skip LLM, use fallback
    
    # Check 2: Do we have RAG context? (gating mechanism)
    if bool(runtime.get("require_rag_context", True)) and not rag_context.strip():
        return None  # No context = no LLM call (safety: prevent hallucinations)
    
    # Build the prompt
    prompt = _build_prompt(
        message, intent, base_reply, next_step, 
        rag_context,  # ← RAG context injected
        **kwargs
    )
    
    # Select provider
    provider = str(runtime.get("provider", "ollama")).lower()
    
    try:
        llm_text = None
        
        if provider == "ollama":
            llm_text = _call_ollama(prompt, runtime)  # TinyLlama
        elif provider == "openai":
            llm_text = _call_openai_compatible(prompt, runtime)  # GPT-4o-mini
        
        # Automatic fallback if primary fails
        if not llm_text and provider == "ollama" and runtime.get("auto_fallback_to_openai"):
            logger.warning("Ollama failed; attempting OpenAI fallback")
            llm_text = _call_openai_compatible(prompt, runtime, fallback_mode=True)
        
        if not llm_text:
            return None
        
        # Safety filtering
        filtered = apply_safety_filter(llm_text)
        if filtered.blocked:
            return filtered.fallback_message
        
        # Enforce sentence limit
        return limit_sentences(filtered.text, settings.chat_reply_max_sentences)
    
    except ReadTimeout:
        logger.warning("LLM request timed out after %ds", runtime.get("request_timeout_seconds"))
        return None
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        return None
```

#### `_call_ollama()` - Call TinyLlama

```python
def _call_ollama(prompt: str, runtime: dict) -> Optional[str]:
    """Call Ollama local model with RAG-grounded prompt."""
    
    url = f"{runtime.get('base_url')}/api/generate"
    
    num_predict = max(24, min(256, int(runtime.get("ollama_num_predict", 96))))
    # Caps token generation at 96 tokens (prevents timeouts)
    
    payload = {
        "model": _active_model_name(runtime),  # tinyllama:latest or fine-tuned
        "prompt": prompt,  # ← Contains RAG context
        "stream": False,
        "options": {
            "num_predict": num_predict,  # Token cap
            "temperature": 0.2,  # Low = deterministic
        }
    }
    
    response = requests.post(
        url,
        json=payload,
        timeout=(5, int(runtime.get("request_timeout_seconds", 60)))  # 60s total
    )
    
    return response.json().get("response", "").strip() or None

# TinyLlama processes the prompt with RAG context and generates:
# "Based on interview preparation guidance, you should:
#  1. Practice coding problems daily with clear thinking
#  2. Prepare 3-4 project stories using the STAR method
#  3. Quantify your achievements with metrics
#  4. Practice explaining your thinking aloud"
```

---

## Data Flow Diagram

```
Input: User Message
│
├─→ [Agent] Generate deterministic response
│   Output: intent, base_reply, next_step, confidence
│
├─→ [RAG Retrieval]
│   1. Rewrite query for clarity
│   2. Vector search in rag/knowledge/
│   3. Rerank with lexical + metadata scoring
│   Output: top-k chunks (interview_prep.txt, portfolio.txt, etc.)
│
├─→ [Format RAG Context]
│   Convert chunks to bullet-list string
│   Output: "- Interview Prep: Practice...\n- Portfolio: Quantify..."
│
├─→ [Build Prompt]
│   Combine: system instructions + RAG context + agent reply + user context
│   Output: Structured prompt with embedded knowledge
│
├─→ [LLM Call] (if enabled AND rag_context exists)
│   TinyLlama + rag_context → refined response
│   Output: LLM-generated text grounded in knowledge base
│
├─→ [Post-processing]
│   Apply safety filter
│   Trim to 8 sentences
│   Output: Final safe, concise response
│
└─→ [Chat Response]
    - reply: Final text
    - citations: Sources (which RAG files were used)
    - response_source: "agent_rag_llm" (agent + RAG + LLM used)
    - llm_used: true
```

---

## Control Flow: When Does RAG→LLM Execute?

```python
# Simplified decision tree

if not runtime_enabled:
    return agent_reply_only  # No LLM call
    
elif require_rag_context and not rag_context:
    return agent_reply_with_rag_fallback  # RAG found nothing; skip LLM
    
elif rag_context:
    return llm_reply  # ← LLM gets RAG context, generates refined response
    
else:
    return agent_reply_only
```

**Result:** LLM only runs when:
1. ✅ `LLM_ENABLED=true`
2. ✅ RAG found relevant context (`rag_context` is not empty)

This prevents the LLM from hallucinating when there's no ground truth.

---

## Configuration

**Environment variables** (in `.env`):

```env
# LLM Control
LLM_ENABLED=true
LLM_PROVIDER=ollama                    # or "openai" / "groq"
LLM_BASE_URL=http://localhost:11434    # Ollama endpoint

# RAG Gating
LLM_REQUIRE_RAG_CONTEXT=true           # ← Critical: only use LLM if RAG found context
RAG_ENABLED=true
RAG_TOP_K=4                            # Retrieve top-4 chunks

# Ollama (Local)
LLM_MODEL=tinyllama:latest             # Base model
LLM_FINETUNED_MODEL=tinyllama-career   # Fine-tuned adapter (optional)
LLM_OLLAMA_NUM_PREDICT=96              # Max tokens to generate (prevents timeout)
LLM_REQUEST_TIMEOUT_SECONDS=60

# OpenAI (Cloud)
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_TOKENS=260

# Groq (Cloud)
GROQ_API_KEY=gsk-...
GROQ_MODEL=llama-3.1-8b-instant
GROQ_MAX_TOKENS=512

# Optional fallback
LLM_AUTO_FALLBACK_TO_OPENAI=false      # Fallback if Ollama fails
```

Runtime overrides can be updated in-memory through `POST /api/v1/llm/config` using payload fields such as `enabled`, `provider`, `openai_model`, `openai_max_tokens`, `groq_model`, and `groq_max_tokens`.

---

## Why This Design Matters

### Without RAG

```python
user_message = "How do I prepare for interviews?"
llm_reply = TinyLlama(user_message)
# → Generic response based on training data
# → Possible hallucinations
# → No connection to your career guidance
# → Reproducible but not domain-specific
```

### With RAG

```python
user_message = "How do I prepare for interviews?"
rag_context = retrieve_from("rag/knowledge/")  # interview_preparation.txt
prompt = build_prompt(user_message, rag_context)
llm_reply = TinyLlama(prompt)
# → Grounded response using your knowledge base
# → Cites specific sources (interview_preparation.txt)
# → Tailored to MTech career guidance domain
# → Reproducible and verifiable
```

---

## Integration Testing

To verify RAG→LLM integration:

```bash
# 1. Start Ollama
ollama serve

# 2. In another terminal, run backend
cd backend
python -m uvicorn app.main:app --reload

# 3. Test via API
curl -X POST http://localhost:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test",
    "message": "How do I prepare for interviews?",
    "context": {"skills": ["Python", "REST APIs"]}
  }'

# Expected response:
# {
#   "reply": "Based on interview preparation guidance...",
#   "response_source": "agent_rag_llm",
#   "rag_citations": [
#     {"title": "Interview Preparation", "source": "interview_preparation.txt"}
#   ]
# }
```

---

## Summary

| Component | Purpose | Source |
|-----------|---------|--------|
| RAG Retrieval | Find relevant knowledge | `rag_service.py` |
| Vector Search | Semantic similarity | `retriever.py` + `vector_store.py` |
| Query Rewriting | Clarity improvement | `query_rewriter.py` |
| Prompt Building | Ground LLM in context | `llm_service.py` |
| LLM Call | Generate response | `_call_ollama()` |
| Post-processing | Safety + formatting | `safety_filter.py` |

**Key insight:** RAG provides the *facts*, LLM provides the *style*. Together, they deliver accurate, well-written career guidance.
