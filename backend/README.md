# TECXE Lens — Backend

Python 3.12+ FastAPI server. The backend is ready to run as a Hugging Face Docker Space.

To deploy on Hugging Face Spaces:

1. Create a new Space and choose the `Docker` SDK.
2. Set the repository root to this `backend/` folder contents.
3. Add any required secrets in Space settings, especially `OPENROUTER_API_KEY`.
4. Let the Space build from [`backend/Dockerfile`](./Dockerfile).

The app listens on port `7860`, which matches the default Hugging Face Docker Space port.
