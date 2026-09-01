# Deployment Guide

## Local Development

### Backend

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\Activate.ps1
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

API: http://localhost:8000
Docs: http://localhost:8000/docs

### Frontend (earth-globe)

```bash
cd earth-globe            # separate project directory
npm install
npm run dev
```

App: http://localhost:5173

## Production Build

### Frontend (earth-globe)

```bash
cd earth-globe
npm install
npm run build       # tsc -b && vite build
# Output: dist/
```

The frontend builds to `dist/` as static files. Serve with any static file server (nginx, Caddy, etc.).

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

Or with uvicorn directly:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Docker

### Build and run

```bash
docker-compose up --build
```

Backend: http://localhost:8000 (API + `/docs`)

### Production deployment (Kubernetes)

For Kubernetes deployment, build images separately:

```bash
docker build -f docker/Dockerfile.backend -t incois-backend:latest .
# earth-globe builds its own static bundle; serve it via any static server/Ingress
```

Then create a Deployment + Service for each. Use an Ingress for HTTPS.

## Environment Variables

See `.env.example` for all configurable variables.

## Performance Tuning

For production with large datasets:

1. **Add caching** — Redis for frequent queries
2. **Use Dask** — for parallel data processing
3. **Use Zarr** — for chunked access
4. **CDN** — Serve static frontend assets via CDN
5. **Database** — PostgreSQL for metadata
6. **Object storage** — S3/MinIO for NetCDF files

## Security Notes

- **DO NOT** ship with default JWT_SECRET
- **DO** set `CORS_ORIGINS` to your actual frontend domain
- **DO** add authentication (OAuth2 / JWT) for production
- **DO** use HTTPS in production
- **DO** rate-limit API endpoints
- **DO** validate all user input

## Health Check

```bash
curl http://localhost:8000/api/health
```

Returns:
```json
{
  "status": "online",
  "service": "INCOIS Ocean Explorer API",
  "version": "1.0.0"
}
```

## Reverse Proxy (nginx example)

```nginx
server {
    listen 80;
    server_name explorer.example.com;

    location /api/ {
        proxy_pass http://backend:8000/;
        proxy_set_header Host $host;
    }

    location / {
        root /var/www/earth-globe;
        try_files $uri $uri/ /index.html;
    }
}
```
