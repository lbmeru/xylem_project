# Bantay Lawa web (React + Vite)

    npm install
    npm run dev        # http://localhost:5173, proxies /api to http://localhost:8000

Start the backend first: `uvicorn project.api:app` (see backend/README.md).
For a deployed build set `VITE_API_URL` to the API's address, then `npm run build`.
