# Personal Document Assistant

A full-stack RAG (Retrieval-Augmented Generation) application that lets you upload personal documents (PDF, TXT, Markdown) and chat with them using hybrid semantic search and Google Gemini.

## Features

- Upload and index PDF, TXT, and Markdown files per user
- Hybrid retrieval combining dense vector search (Gemini embeddings + pgvector) and full-text search, fused with Reciprocal Rank Fusion (RRF)
- AI-generated answers grounded in your documents with source citations
- Per-user auth and document isolation via Supabase Auth (email + password)
- Serverless deployment on Vercel (FastAPI + Mangum ASGI adapter)

## Live Demo
