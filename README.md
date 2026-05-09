# Financial RAG API

A FastAPI-based financial document management system with RAG (Retrieval-Augmented Generation) capabilities.

## Features
- JWT Authentication
- Role-based access control (Admin, Financial Analyst, Auditor, Client)
- Upload and manage financial documents (PDF, TXT)
- Semantic search using Qdrant vector database
- AI-powered Q&A using Ollama (llama3)

## Tech Stack
- FastAPI
- SQLAlchemy + SQLite
- Qdrant (vector DB)
- SentenceTransformers (all-MiniLM-L6-v2)
- FlashRank (reranker)
- LangChain + Ollama

## Setup
1. Clone the repo
2. Create virtual environment: `python -m venv venv`
3. Install dependencies: `pip install -r requirements.txt`
4. Create `.env` file (see below)
5. Run: `uvicorn app.main:app --reload`

## Environment Variables
Create a `.env` file: