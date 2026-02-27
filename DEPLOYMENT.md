# TriGuard AI Deployment Guide

This guide covers deploying TriGuard AI to a production environment using Docker Compose.

## Prerequisites

- Docker Engine & Docker Compose installed
- Port 80 and 8000 available on the host machine
- API keys for MongoDB, Groq, HuggingFace, and Tavily

## Quick Start

1. **Clone and Configure**:
   Copy the `.env.example` in the `backend/` folder to `.env` and fill in your actual production keys.

   ```bash
   cp backend/.env.example backend/.env
   # Edit backend/.env
   ```

2. **Build and Spin Up Containers**:
   Execute docker-compose from the project root:

   ```bash
   docker-compose up -d --build
   ```

3. **Verify Deployment**:
   - The React frontend is available at `http://localhost:80` (or your domain).
   - The FastAPI backend is exposed at `http://localhost:8000`.
   - You can verify the backend health endpoint at `http://localhost:8000/api/v3/health`.

## Notes on Architecture

- **Backend**: Runs on Python 3.10 with FastAPI, deployed securely behind Gunicorn using Uvicorn workers. All file system writes (audio/images) are mapped to Docker volumes for persistence across restarts.
- **Frontend**: A multi-stage Docker build handles the Node.js/Vite build process and serves static files using an Nginx alpine image.
