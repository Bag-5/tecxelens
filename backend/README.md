# TECXE Lens — Backend

Python 3.12+ FastAPI server. The backend is ready to run as a Render web service or a Docker-based deploy target.

To deploy on Render:

1. Point the service root at `backend/`.
2. Use the build command `pip install -r requirements.txt`.
3. Use the start command `uvicorn main:app --host 0.0.0.0 --port $PORT`.
4. Add `OPENROUTER_API_KEY`, `FRONTEND_ORIGIN`, and optionally `NVD_API_KEY`.
5. If large PDFs are slow, reduce `MAX_PDF_PAGES` to cap how much text gets extracted per upload.

The app exposes `/health` for the Render health check.
