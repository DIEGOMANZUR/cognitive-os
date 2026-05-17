# Cognitive OS — Architecture

> **Status (2026-05-17, Phase 39 — residual risks closed):** stack
> operational at commercial grade. Verified counts (no inflation): **122
> REST endpoints** (100 Cognitive-OS-owned + 26 orchestration), **15 Celery
> tasks** across **5 queues** (`default`, `ingestion`, `agent_longrun`,
> `maintenance`, `mail`), **16 Alembic migrations** (head
> `202605160002`), **20 Next.js views** under `frontend/app/views/*.tsx`
> (including `AssistView`, `GoogleOpsView` and `ResearchView` — animated
> plan over SSE), **21 MCP servers** wired via the OpenCode cockpit,
> **15 skills**, 7 subagents, 7 slash commands. Local runtime:
> **DeepSeek V4 Pro** (`deepseek-v4-pro`); secondary Kimi
> K2.6-code-preview; vision GLM-4.6v primary, Kimi 2.6 fallback.
>
> Phase 39 closed every technical residual risk: pluggable rate limiter
> (memory/Redis), `/system/credentials-status` admin endpoint with the
> live 21-credential inventory (never returns values), `workflow.v1`
> ActionRequest export/import, self-healing Google OAuth
> (`auth_google.py` skips the browser when an existing token can
> refresh), `init_credentials.sh` operator wizard, request-scoped
> `X-Request-ID` propagation, approval reaper
> (`APPROVAL_PENDING_MAX_HOURS=48`), four-eyes approvals
> (`APPROVAL_REQUIRE_FOUR_EYES=true`) and AuditEvent symmetry between the
> REST and Telegram approval paths.
>
> QA snapshot: **642 pytest passed, 1 skipped, 20 deselected**;
> ruff/mypy/lint/build, Compose config, Alembic head with no drift,
> `git diff --check`, `pre-commit run --all-files` (6 hooks) and
> `detect-secrets scan` all green.

Cognitive OS is a local-first cognitive operating system. LangGraph orchestrates
flows, DeepAgents do the deep work, **OpenHarness optionally augments the `research`
path** (upstream `QueryEngine`), and PostgreSQL/Weaviate/Neo4j/Redis provide
the persistence and retrieval substrate. The whole stack is designed to be
auditable, with human-in-the-loop gates around any sensitive action.

## High-level wiring

```
┌──────────────┐   ┌────────────────────────────────────────────────────┐
│   Next.js    │   │                    FastAPI app                      │
│  (frontend)  │──▶│  /chat /threads /documents /document-analysis      │
└──────────────┘   │  /jobs /approvals /health/dashboard /deepagents/*  │
                   │  /actions/* /mail/* /research/* /langsmith/*       │
                   └────────────────────────┬───────────────────────────┘
                                            │
                          ┌─────────────────┼─────────────────┐
                          ▼                 ▼                 ▼
                  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
                  │  LangGraph   │  │ Celery tasks │  │  AsyncSQL    │
                  │ orchestrator │  │ + Redis cola │  │ (Postgres)   │
                  └──────┬───────┘  └──────┬───────┘  └──────────────┘
                         │                 │
        ┌────────────────┼─────────────────┼──────────────────────┐
        ▼                ▼                 ▼                      ▼
 ┌────────────┐  ┌──────────────┐  ┌────────────────┐   ┌───────────────────┐
 │  retrieve  │  │  DeepAgents  │  │ Document       │   │ OpenShell sandbox │
 │  (Weaviate │  │  (research,  │  │ Analysis       │   │ (vendor opcional) │
 │  + RAG +   │  │  document_   │  │ DeepAgent +    │   │                   │
 │  reranker) │  │  analysis)   │  │ Evidence       │   │                   │
 │            │  │              │  │ Ledger +       │   │                   │
 │            │  │              │  │ evaluators     │   │                   │
 └─────┬──────┘  └──────┬───────┘  └────────┬───────┘   └─────────┬─────────┘
       │                │                   │                     │
       ▼                ▼                   ▼                     ▼
┌────────────┐   ┌───────────────┐   ┌────────────────┐   ┌──────────────┐
│ Weaviate   │   │ DeepAgent     │   │ workspaces/    │   │ docker (host)│
│ (chunks    │   │ skills/memory │   │   analysis/    │   │ vendor of    │
│ + embed.)  │   │ + workspace   │   │   *.csv,       │   │ openshell    │
│            │   │ filesystem    │   │   *.md,        │   │ deepagent    │
│            │   │               │   │   *.docx       │   │              │
└────────────┘   └───────────────┘   └────────────────┘   └──────────────┘
```

OpenHarness (optional `openharness-ai` extra): on the `research` route, LangGraph may run the upstream **QueryEngine** loop before DeepAgents share the same task workspace (`deepagent_mirror` mode by default). Modes **`prelude_merge`** vs **`short_circuit`** and tool presets are documented in `docs/OPENHARNESS_FUSION.md`.

## Operational state

PostgreSQL is the operational source of truth: users, threads, documents,
pages, chunks, jobs, job events, human approvals, audit events, DeepAgent
memory and proposals, DeepAgent skill usage records, document analysis results,
mail accounts, mail messages and mail send logs all live here. Schema lives
under `backend/alembic/versions/`.

## LangGraph thread state

The compiled graph uses a checkpointer:

* **Production / `uvicorn`**: the FastAPI lifespan opens a `PostgresSaver`
  via `cognitive_os.agents.graph.postgres_checkpointer()`. Threads survive
  process restarts, and `/threads/{id}/resume` keeps working.
* **Tests / fallback**: if Postgres is unreachable when the app starts,
  the lifespan logs a warning and falls back to `MemorySaver`. The
  graph stays usable; threads simply do not persist across restarts.

The active backend is reported in `GET /health/dashboard` as the
`checkpointer` component (`status=ok` for postgres, `configured` for memory).

## Core nodes

* `router_node` — picks `research` / `legal` / `comm` / `social`. Forces
  `legal` whenever the request carries explicit `doc_ids` so the document
  analysis path runs without keyword matching.
* `retrieve_context_node` — Weaviate hybrid search + lazy reranker. Errors
  are downgraded to "no context" rather than killing the request.
* `research_node` — optional **OpenHarness** `QueryEngine` prelude (when
  `ENABLE_OPENHARNESS_RESEARCH` and the package are present), then the DeepAgent
  research subagent with `openharness_prelude` merged into the user message when
  `OPENHARNESS_RESEARCH_PIPELINE=prelude_merge` (default). `short_circuit` returns
  OpenHarness output without calling DeepAgents. Deterministic citation-aware RAG
  fallback if DeepAgents does not yield substantive content (`docs/OPENHARNESS_FUSION.md`).
* `legal_node` — when document analysis is requested, builds a
  `DocumentAnalysisTask` (carrying `doc_ids`, `case_id`, modes) and delegates
  to `DocumentAnalysisService`. Drafts always trigger a `HumanReviewItem`.
* `human_review_node` — interrupts the graph and awaits approve/edit/reject.
* `error_node` / `final_response_node` — recovery and serialization.

## Connections at runtime

* **Frontend → FastAPI**: JWT bearer; CORS allows `localhost:3000`.
* **FastAPI → LangGraph**: `_api_graph` is a module-level compiled graph;
  the lifespan rebinds it to a Postgres-backed graph at startup.
* **FastAPI → OpenHarness bridge**: llamada síncrona `run_openharness_research_sync`
  desde `cognitive_os.integrations.openharness_research`, solo en `research_node`
  cuando el extra está instalado y `ENABLE_OPENHARNESS_RESEARCH` (`docs/OPENHARNESS_FUSION.md`).
* **FastAPI → Celery**: long jobs (`ingest_pdf`, `run_deepagent_task`,
  `run_openshell_task`, `run_document_analysis`, `sync_personal_mail`) go
  through Redis queues with separate routing keys (`ingestion`, `agent_longrun`,
  `maintenance`, `mail`, `default`).
* **Celery → DeepAgents**: tasks build a `DeepAgentTask` and call
  `run_deepagent_task` / `DocumentAnalysisService.run_analysis_as_job`.
  Each tool call passes through the policy layer (`tools/policy.py`) and
  gets audited.
* **DeepAgents → RAG**: `search_within_allowed_docs` filters Weaviate hits
  to the agent's `allowed_doc_ids` and to `allowed_page_ranges`.
* **Document Analysis → exporters**: emits `result.json`, `report.md`,
  `evidence_matrix.csv`, `timeline.csv`, `contradictions.csv`, optional
  `report.docx`. CSVs are downloadable via
  `GET /document-analysis/{task_id}/download/csv/{kind}`.
* **OpenShell sandbox**: disabled by default. When enabled, runs vendor
  CLI inside Docker, requires explicit human approval for risky inputs,
  records every run in `audit_events`.
* **Action plane**: `backend/src/cognitive_os/actions/` exposes preview-first
  browser, computer, Gmail, GoDaddy and Office-document capability checks plus
  persistent `ActionRequest` records. `backend/src/cognitive_os/mail/` provides
  the newer personal mail lane: GoDaddy IMAP/SMTP, Gmail label reader, Postgres
  persistence, written proposals and approval-only send. `computer_organize`,
  document generation, browser preview/interactive, DNS and mail send execute
  only through guarded services.
* **Memory consolidation**: Celery beat fires `consolidate_all_deepagent_memory`
  daily, which dispatches per-agent consolidation jobs (`research`,
  `document-analysis`). Resulting memory is stored as proposals; only an
  approved proposal becomes active memory.

## Failure modes & graceful degradation

| Component down              | Effect                                                  |
| --------------------------- | ------------------------------------------------------- |
| Postgres                    | Lifespan falls back to `MemorySaver`; jobs/auth fail.   |
| Redis                       | API still responds; Celery jobs cannot be enqueued.     |
| Weaviate / embeddings       | `_safe_retriever` returns `[]`; chat replies "sin evidencia". |
| Reranker model not present  | Lexical fallback ranker; spec compliant.                |
| Neo4j                       | Ingestion warns and continues; chat path unaffected.    |
| LLM provider                | Router falls back to deterministic keyword routing.     |
| OpenHarness extra missing / disabled | Research path skips QueryEngine; DeepAgents + fallback unchanged. |
| Mail IMAP/SMTP              | `/mail/status` reports degraded/errors; no auto-send.   |

## Security controls

* Every mutating endpoint requires a JWT. The "admin" claim is enforced
  whenever `ADMIN_USER_IDS` is non-empty.
* Tool risk levels: `READ_ONLY`, `REVERSIBLE_WRITE`, `EXTERNAL_ACTION`,
  `DANGEROUS`, `SANDBOX_EXECUTE`. External actions and dangerous tools
  always pass through `human_approvals`.
* PII redaction is the default in `LANGSMITH_TRACING` and audit metadata.
* OpenShell never touches `~`, `.env`, or the repo root.
* Action plane defaults to disabled and dry-run. Browser domains, filesystem
  roots, Gmail scopes, personal mail send and GoDaddy writes are explicit
  policy surfaces.

## Where to look next

* `backend/src/cognitive_os/api/app.py` — wiring, lifespan, endpoints.
* `backend/src/cognitive_os/agents/graph.py` — orchestrator nodes & routing.
* `backend/src/cognitive_os/deepagents/` — controlled DeepAgents factory,
  research and document analysis subagents.
* `backend/src/cognitive_os/ingestion/pipeline.py` — PDF → pages → chunks →
  Weaviate + Neo4j flow.
* `backend/src/cognitive_os/workers/tasks.py` — Celery task definitions.
* `backend/src/cognitive_os/mail/` — personal mail IMAP/SMTP/Gmail-label lane.
* `docs/OPENHARNESS_FUSION.md` — OpenHarness + LangGraph + DeepAgents on `research`.
* `docs/ACTION_PLANE.md` — browser/computer/Gmail/GoDaddy action model.
* `docs/SECURITY.md`, `docs/DEEPAGENTS_INTEGRATION.md`,
  `docs/DOCUMENT_ANALYSIS_AGENT.md`, `docs/OPENSHELL_SANDBOX.md` — deep dives.
