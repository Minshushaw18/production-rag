# RAG Chatbot Architecture

## Overview

This document describes the end-to-end flow of the RAG (Retrieval-Augmented Generation) chatbot system, from user query to response, including guardrails, routing, retrieval, and memory.

## Flow Diagram (Text Representation)

```
User
  │
  ▼
Streamlit UI
  │
  ▼
FastAPI /query
  │
  ▼
NeMo Guardrails ──── Blocked ────► (returns directly to Streamlit UI)
  │
  │ Pass
  ▼
Planner Node
  │
  ├── Conversational ──► Responder Node ──► Streamlit UI
  │
  └── Technical ──► Retriever Node
                        │
                        ▼
                  FlashRank Local Reranker
                        │
                        ▼
                  Responder Node ──► Streamlit UI

Responder Node ◄──(read/write, dashed)──► LangGraph MemorySaver
```

## Components

| Component | Role |
|---|---|
| **User** | Initiates the query via the UI |
| **Streamlit UI** | Front-end interface where the user submits queries and views responses |
| **FastAPI `/query`** | Backend API endpoint that receives the query from the UI and routes it into the pipeline |
| **NeMo Guardrails** | Safety/validation layer; queries are either **Blocked** (short-circuited back to the user) or allowed to **Pass** into the pipeline |
| **Planner Node** | Decides whether the query is **Conversational** or **Technical**, routing accordingly |
| **Responder Node** | Generates the final response for conversational queries, or after retrieval for technical queries; sends the response back to the Streamlit UI |
| **Retriever Node** | Handles retrieval of relevant documents/context for technical queries |
| **FlashRank Local Reranker** | Reranks retrieved documents locally to improve relevance before passing them to the Responder Node |
| **LangGraph MemorySaver** | Persistent memory store; the Responder Node reads from and writes to it (dashed bidirectional connection) to maintain conversational context |

## Flow Summary

1. The **User** submits a query through the **Streamlit UI**.
2. The UI forwards the request to **FastAPI's `/query`** endpoint.
3. The query passes through **NeMo Guardrails**:
   - If **blocked**, the response is routed directly back to the Streamlit UI.
   - If it **passes**, it proceeds to the **Planner Node**.
4. The **Planner Node** classifies the query:
   - **Conversational** queries go straight to the **Responder Node**.
   - **Technical** queries go to the **Retriever Node**.
5. The **Retriever Node** fetches relevant documents, which are passed to the **FlashRank Local Reranker** for local reranking.
6. Reranked results are passed to the **Responder Node**, which generates the final answer.
7. The **Responder Node** interacts with **LangGraph MemorySaver** to persist/retrieve conversational memory.
8. The final response flows back to the **Streamlit UI** for the user to see.