# TECXE Lens — Backend

Python 3.12+ FastAPI server. The backend is ready to run on Replit.

To deploy on Replit:

1. Open the repo in Replit.
2. Use the root [`.replit`](../.replit) file to start `uvicorn` from `backend/`.
3. Add required secrets in the Replit Secrets panel, especially `OPENROUTER_API_KEY`.
4. Replit should expose port `8000`.

The app exposes `/health` for health checks.
