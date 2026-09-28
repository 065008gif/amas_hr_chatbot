---
title: Nia HR Assistant (demo)
emoji: 🗂️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
short_description: RAG HR helpdesk API for a fictional company (college project)
---

# Nia: HR helpdesk assistant API (college project)

Backend for the Nexora People Portal. **Nexora Technologies Limited is fictional**; its 9 policy
documents and 300 employees are invented for a college project. Nia is an AI assistant, not HR advice.

- `GET /health` - status of the index, models and AI providers
- `POST /chat` - cited answers from the policy PDFs (hybrid BM25 + dense retrieval, reranking, page-verified citations)
- `GET /docs-list`, `GET /pdf/{doc_id}` - the policy documents

Secrets `OLLAMA_API_KEY` and `GEMINI_API_KEY` are set as Space secrets, never in code.
Tickets and logs are kept in `/tmp` and reset when the Space restarts (demo).
