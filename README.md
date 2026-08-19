# Personal Document Assistant

A full-stack RAG (Retrieval-Augmented Generation) application that lets you upload personal documents (PDF, TXT, Markdown) and chat with them using hybrid semantic search and Google Gemini.

## Features

- Upload and index PDF, TXT, and Markdown files per user
- Hybrid retrieval combining dense vector search (all-MiniLM-L6-v2 embeddings via ONNX Runtime + pgvector) and full-text search, fused with Reciprocal Rank Fusion (RRF)
- AI-generated answers grounded in your documents with source citations, streamed token by token
- Per-user auth and document isolation via JWT (bcrypt password hashing, httpOnly cookie)
- React frontend on Vercel, FastAPI backend on Render (see Deployment)

## Deployment

The frontend is static and deploys to Vercel unchanged. The backend runs as a
persistent process on Render via [backend/render.yaml](backend/render.yaml).

**Why the backend is not serverless.** `embedding_service` downloads a ~90MB
ONNX model on first use. On a serverless function that download repeats on
every cold start and exceeds the request timeout. A long-lived process pays it
once — and the Render build step bakes the model in, so even the first request
is fast. Streaming responses also work end to end, which a Lambda-style adapter
cannot do because it buffers the whole body before returning it.

### Backend (Render)

1. Render dashboard → **New** → **Blueprint**, point it at this repo.
2. Fill the secrets marked `sync: false` in `render.yaml`: `SUPABASE_URL`,
   `SUPABASE_SERVICE_KEY`, `GEMINI_API_KEY`, and `FRONTEND_URL` (your Vercel
   origin). `JWT_SECRET` is generated for you.
3. Note the service URL, e.g. `https://personal-doc-assistant-api.onrender.com`.

On the free plan the service sleeps after inactivity; the first request after a
sleep waits for the process to start.

### Frontend (Vercel)

Point the API rewrite in [frontend/vercel.json](frontend/vercel.json) at the
Render URL:

```json
{ "rewrites": [
  { "source": "/api/:path*", "destination": "https://<your-service>.onrender.com/:path*" }
] }
```

Keep the rewrite rather than setting `VITE_API_URL` to the backend directly.
The rewrite makes the browser treat API calls as same-origin, so the `SameSite=Lax`
auth cookie is still sent and no CORS preflight is involved. Calling the backend
origin directly would drop the cookie on every request.

`backend/vercel.json` is left over from the previous serverless setup and is no
longer used.

## Live Demo
