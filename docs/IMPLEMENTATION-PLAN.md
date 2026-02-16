# Implementation plan: Orchestrator and Memory Layer

Orchestrator and Memory Layer live in the **pmp-admin-panel** repo and run in a **separate container** from the admin UI. The **memory layer is Mem0** (open source): it already provides semantic search, graph, add/search, user/session scoping, conflict resolution – roughly half of what we need. We add on top: human confirmation, source tracking, and orphaning (ABLE Core ideas).

---

## Target architecture

```
Admin UI (container 1)   -->   Orchestrator (container 2)   -->   LLM API (pmp-llm)
    pmp-admin-panel              pmp-admin-panel                    separate repo
                                      |
                                      v
                              Mem0 (memory layer)
                              + our gate: confirm, source, orphaning
```

- **Container 1:** Admin UI (static frontend, nginx).
- **Container 2:** Orchestrator (FastAPI); session store; context building; calls LLM API; **Mem0** for persistent memory (add/search); gate for human confirmation and source/orphaning.

---

## Mem0: what we use as-is

- **Add memory:** `add(messages, user_id, metadata)` – Mem0 infers facts, conflict resolution, stores in vector (+ optional graph).
- **Search:** semantic search, optional reranking; user/session scoping via `user_id`, metadata.
- **Graph memory:** entity relationships for multi-hop recall (optional).
- **REST API / OpenAI compatibility** for integration.
- **Self-hosted OSS** – we run it ourselves, no vendor lock-in.

Ref: [Mem0 docs](https://docs.mem0.ai) (memory operations, open-source features).

## What we add on top of Mem0 (ABLE Core)

| Need | Mem0 | We add |
|------|------|--------|
| Human confirmation | Auto-adds inferred facts | Gate: propose -> show to user -> only on confirm call Mem0.add |
| Source tracking | No provenance | Store source (e.g. file, revision) in metadata; our layer tracks it |
| Orphaning | No | When source changes, mark/delete or re-request confirm for affected memories |

---

## Phases

### Phase 1: Orchestrator + session + Mem0

- **Orchestrator** (FastAPI): session store (in-memory or Redis); `POST /session`, `GET /session/{id}`, `POST /chat`; build context (system prompt + recent messages), call LLM.
- **Mem0 integration:** after chat turn (or on explicit “save”), call Mem0 `add(messages, user_id=session_id, metadata)` so long-term memory is populated; on next request, Mem0 `search` and inject retrieved memories into context.
- **Deploy:** orchestrator + Mem0 in Docker (Mem0 OSS in same container or separate); admin and orchestrator URLs via env.

### Phase 2: Human confirmation + source + orphaning

- **Propose/confirm:** orchestrator proposes “memories to add” (e.g. from LLM turn); UI shows them; only on user confirm we call Mem0.add.
- **Source in metadata:** when adding, pass `metadata={"source": "chat", "session_id": "...", "revision": "..."}` or file/repo ref for code-related facts.
- **Orphaning:** when a source changes (e.g. file updated), query Mem0 by metadata, mark or delete affected memories, or surface “re-confirm?” in UI.
- **Tools:** todo_write, question; persist in session; return to UI.

### Phase 3: Publish and target repo

- **Publish:** orchestrator (or dedicated service) receives “publish” request, takes session artifacts (generated files), pushes to target repo (branch, commit, PR) via Git API. No code committed to admin repo.

---

## Where things live

| Component        | Repo              | Container        |
|------------------|-------------------|------------------|
| LLM API          | llm-test-for-pmp-api (pmp-llm/) | own (pmp-llm)    |
| Admin UI         | pmp-admin-panel   | own (admin UI)   |
| Orchestrator     | pmp-admin-panel   | **separate** (orchestrator) |
| Memory layer     | **Mem0** (OSS) + orchestrator gate (confirm/source/orphaning) | Mem0 same or separate container; gate in Orchestrator |

---

## Orchestrator API (Phase 1)

- `POST /session` – create session, returns `{ "session_id": "..." }`.
- `GET /session/{session_id}` – get session (messages, optional task_plan, artifacts).
- `POST /chat` – body: `{ "session_id": "...", "content": "user message" }`. Optional: `"stream": true`. Returns full response or SSE stream.
- `GET /health` – liveness.

Context sent to LLM: system prompt (configurable) + `resolved_context` (if any) + last N messages from session.

---

## Current implementation status

What is described in the **final documentation** (AI-CUSTOMIZATION-PLATFORM.md, OPENCODE-IMPLEMENTATION.md, Phase 2/3) vs what is **implemented** in pmp-admin-panel today:

| Feature | Where it's described | Implemented? | Where in code (if yes) |
|--------|----------------------|---------------|------------------------|
| **Session + chat** | Phase 1 | Yes | `orchestrator/main.py`, `frontend/Chat.tsx` |
| **Mem0 add/search** | Phase 1 | Yes | `orchestrator/memory_layer.py`, `context.py` |
| **Session list + switcher** | UI spec | Yes | `GET /sessions`, `Chat.tsx` session bar |
| **Context: last N messages** | Phase 1 | Yes | `context.py` `build_messages(max_recent=20)` |
| **Context window management** | OPENCODE: "Auto-compact при 95% лимита" | **No** | - |
| **Summarization of old messages** | OPENCODE: "суммаризирует старые сообщения" | **No** | Only last 20 turns sent; no token count, no summarization |
| **Task breakdown (разбиение на шаги)** | AI-CUSTOMIZATION: "разбивает сложные задачи на шаги" | **No** | - |
| **TODO from LLM (todo_write)** | Phase 2, AI-CUSTOMIZATION: "LLM вызывает todo_write" | **No** | Session has `task_plan` field but no tools; LLM cannot call tools |
| **TODO in UI** | AI-CUSTOMIZATION: "TODO progress", OPENCODE: TaskList | **No** | `TodoList.tsx` is placeholder "Coming soon"; no data from session.task_plan |
| **question tool (уточнения)** | Phase 2, AI-CUSTOMIZATION: "Уточнения у пользователя" | **No** | No tool calling; no `resolved_context` from user answers |
| **resolved_context in context** | Session model | Partial | Injected in `build_messages` if present; never populated by flow |
| **Human confirmation (Mem0)** | Phase 2, ABLE Core | **No** | Memories added automatically after each turn |
| **Source / orphaning** | Phase 2 | **No** | - |
| **Code preview (Monaco)** | AI-CUSTOMIZATION, OPENCODE | **No** | `CodePreview.tsx` placeholder "Coming soon" |
| **Publish to target repo** | Phase 3 | **No** | `PublishButton` exists but no backend |

**Summary:** Only **Phase 1** is done (orchestrator, session, Mem0 add/search, simple context). Context window control, summarization, task breakdown, TODO tools + UI, question tool, confirm/source/orphaning, code preview, and Publish are **not implemented**; they are only specified in the docs.

### What Mem0 already gives us (and we use)

Mem0 is a **memory** layer, not an agent/orchestrator. It covers:

| Mem0 capability | We use? | Note |
|-----------------|--------|------|
| **Add** – LLM extracts facts from messages, stores in vector (+ conflict resolution) | Yes | After each turn we call `add(messages, user_id=session_id)`. This is Mem0's "summarization": it does not store raw chat, it extracts and stores facts. So long-term "summary" of past convos is in Mem0. |
| **Search** – semantic retrieval by query | Yes | Before each request we `search(last_user_message, user_id=session_id)` and inject results into system prompt. So "relevant past context" comes from Mem0, not from sending full history. |
| **get_all** – get all memories for user/session (with filters) | No | We could add: `get_all(filters={"user_id": session_id})` and inject into context to give LLM "everything we remember for this session" in addition to search. Optional. |
| **Update / Delete** | No | For Phase 2 (orphaning, invalidation) we would use these. |
| **Graph memory** (entity relations) | No | OSS supports it; we use only vector. Can enable for multi-hop recall. |
| **Memory types** (session vs user vs org) | Partial | We use `user_id=session_id` so effectively session-scoped. Could use distinct user_id for cross-session memory. |

So: **context/summarization in the "memory" sense** – Mem0 does it (add = extract facts, search = recall). We use it. We do **not** send full chat history to the LLM; we send last N messages + Mem0 search results. What we do **not** have is: (1) token counting and trimming of the **message list** (the 20 turns we send) if the model has a small context window; (2) optional "rolling summary" of the **chat transcript** (separate from Mem0 facts) if we wanted to compress old turns into one summary message. Those are orchestrator-level choices, not Mem0.

**TODO / task breakdown** – Mem0 does **not** provide this. Mem0 = "what do we remember (facts)". TODO = "what are we doing (tasks)". Tasks live in session state and tools (`todo_write`/`todoread`); the orchestrator must implement tool calling and persist `task_plan`, and the UI must show it. So those features are outside Mem0 and still to be implemented.
