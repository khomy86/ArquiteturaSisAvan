# UALFlix

A small video platform split into services: upload a video, it gets processed in the background (thumbnail and duration via ffmpeg), and then it can be streamed in the browser with seeking. An admin panel behind a login lets you edit, hide, restore or permanently delete videos.

The focus is on the architecture: load-balanced stateless services, a shared job queue, object storage, and PostgreSQL streaming replication.

## Architecture

```
browser ──▶ nginx :8080
              ├── /             → web
              ├── /admin/       → admin_panel
              ├── /api/         → catalog-service-1, catalog-service-2
              │                     ├──▶ PostgreSQL primary ──WAL──▶ replica-1, replica-2
              │                     ├──▶ Redis (upload queue, job status, change events)
              │                     └──▶ MinIO
              ├── /stream/      → streaming-service-1, streaming-service-2 ──▶ MinIO
              └── /thumbnails/  → MinIO (public-read bucket)
```

| Service | What it does |
| --- | --- |
| `loadbalancer` | nginx. Single entry point, round-robins `/api/` and `/stream/` across two instances each |
| `web` | Public React front end: browse, watch, upload |
| `admin_panel` | React admin panel, served under `/admin/` |
| `catalog-service-1`, `-2` | FastAPI. Video metadata, uploads, admin API, auth, and a background worker that processes uploads |
| `streaming-service-1`, `-2` | FastAPI. Streams video from MinIO with HTTP range support, so seeking works |
| `db` | PostgreSQL 16 primary |
| `db-replica-1`, `-2` | Hot standbys cloned with `pg_basebackup`, kept in sync through physical replication slots |
| `redis` | Upload job queue, job status, and pub/sub for live catalog updates |
| `minio` | S3-compatible storage for the original files and thumbnails |

### Upload flow

1. `POST /api/videos/upload` creates a `pending` row, streams the file into the `videos` bucket and pushes a job onto a Redis list. The response comes back straight away with an `upload_id`.
2. Each catalog instance runs a worker thread that blocks on that list, so whichever instance is free takes the job, not necessarily the one that received the upload.
3. The worker downloads the file, reads the duration with `ffprobe`, grabs a frame for the thumbnail, uploads it and marks the video `completed` (or `failed` if the file isn't a readable video).
4. The front end polls `GET /api/uploads/{upload_id}/status`. Status lives in Redis, so any instance can answer.

### Surviving a crashed worker

A worker claims a job with `BLMOVE`, which atomically moves it from the queue into a processing list owned by that worker, and removes it only once it's finished. Each worker also refreshes a heartbeat key with a 30-second expiry, from a separate thread so it keeps going during a long ffmpeg run.

If a catalog instance dies mid-job, its heartbeat expires and the other instance moves the abandoned job back onto the queue and processes it. Reprocessing is safe because every step overwrites the same objects and row. A job that fails this way three times is marked `failed` rather than retried forever. Errors caused by the upload itself (a file ffmpeg can't read) fail straight away; errors from the infrastructure (database or storage unreachable) put the job back to be retried.

You can see this happen by killing an instance with `podman kill -s KILL` (or `docker kill`) while it processes a large upload: about 30 seconds later the other instance logs `Requeued upload ...` and finishes it.

### Load balancing and failover

nginx round-robins across the two instances of each service and resolves their names at runtime, so a restarted container is picked up at its new address. The connect timeout is 2 seconds instead of nginx's default 60, so when an instance is down, a request that lands on it fails over to the other one almost immediately (for idempotent requests), and nginx then stops sending it traffic for 10 seconds.

Uploads and logins are rate limited per client address (10 per minute, with a burst of 5), and over-limit requests get a JSON `429`. Under rootless Podman every client reaches nginx from the same address, so there the limits apply to all clients together.

### Live updates

Whenever a video finishes processing, or is edited, deleted or restored, the catalog service publishes a message on a Redis channel. `GET /api/events` streams those messages to the browser as server-sent events. Every catalog instance subscribes to the channel, so a page connected to one instance still sees changes made through the other. The public site and the admin panel both reload their lists when an event arrives, and a video page that's open when its video is deleted swaps the player for a message.

### Authentication

The admin API (`/api/admin/*`) requires a JWT bearer token from `POST /api/auth/login`. Passwords are hashed with Argon2. The admin account is created on startup from `ADMIN_USERNAME` / `ADMIN_PASSWORD`, and changing the password there and restarting updates it. Both catalog instances share `JWT_SECRET`, so a token from one is valid on the other.

Browsing, watching and uploading from the public site don't require an account.

## Running it

You need either **Docker** with Compose v2, or **Podman** with `podman-compose`. Nothing else is needed on the host.

```bash
cp .env.example .env     # optional: every setting has a development default
docker compose up --build
# or
podman compose up --build
```

The first build takes a few minutes. Then open:

| URL | |
| --- | --- |
| http://localhost:8080 | Front end |
| http://localhost:8080/admin/ | Admin panel (default login `admin` / `admin`, set it in `.env`) |
| http://localhost:8080/api/docs | Catalog API docs (Swagger UI, with an Authorize button for the admin routes) |
| http://localhost:9001 | MinIO console |

The databases are published on localhost only: the primary on 5432 and the replicas on 5433 and 5434. To see replication working:

```bash
docker compose exec db-replica-1 psql -U ualflix -c "select id, title from videos"
```

The port is 8080 rather than 80 because rootless Podman can't bind ports below 1024. Change it with `HTTP_PORT` in `.env`.

## API

Paths below are relative to `/api`.

| Method | Path | Auth | |
| --- | --- | --- | --- |
| POST | `/auth/login` | | Form fields `username`, `password`. Returns `{access_token, token_type}` |
| GET | `/auth/me` | admin | Current admin |
| GET | `/videos` | | Videos that are processed and not deleted |
| GET | `/videos/{id}` | | |
| POST | `/videos/upload` | | `multipart/form-data`: `title`, `description`, `file` |
| GET | `/uploads/{upload_id}/status` | | `pending`, `processing`, `completed` or `failed` |
| GET | `/events` | | Server-sent events, each `{"action": ..., "video_id": ...}` |
| GET | `/admin/videos` | admin | Every video, including failed and deleted |
| PATCH | `/admin/videos/{id}` | admin | Update `title` and/or `description` |
| DELETE | `/admin/videos/{id}` | admin | Soft delete. `?permanent=true` also removes the files and upload status |
| POST | `/admin/videos/{id}/restore` | admin | Undo a soft delete |

Outside `/api`: `GET /stream/{id}` (supports `Range`) and `GET /thumbnails/{id}.jpg`.

## Development

Backend tests use SQLite, fakeredis and a stubbed MinIO, so they run without any containers:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

### Database migrations

The schema is managed with Alembic, and the catalog service runs `upgrade head` on startup, holding a PostgreSQL advisory lock so that the two instances don't both migrate at once. After changing `catalog_service/models.py`, generate a migration from the repository root with the stack running:

```bash
export DATABASE_URL=postgresql://ualflix:ualflix@localhost:5432/ualflix
alembic -c catalog_service/alembic.ini revision --autogenerate -m "describe the change"
```

Review the generated file in `catalog_service/migrations/versions/`, and restart the catalog services to apply it. CI checks that the migrations and models match on every push.

### Front end

For front-end work, keep the stack running and start the dev server; `/api` requests are proxied to `localhost:8080`:

```bash
cd web            # or admin_panel
npm install
npm start
```

## Project layout

```
catalog_service/    FastAPI catalog: routes, auth, models, queue, upload worker, migrations
streaming_service/  FastAPI range-request video streaming
web/                Public React front end
admin_panel/        React admin panel
nginx/              Load balancer config
postgres_config/    Primary init script and standby entrypoint for replication
docker/             Dockerfiles for the application images
tests/              pytest suite
```

## Known limitations

- Videos are stored and served as uploaded, with no transcoding, so a format the browser can't play (such as some `.mkv` files) will upload fine but won't play.
- A soft-deleted video's file stays in storage so it can be restored, which means its `/stream/{id}` URL still works for anyone who already has it.
- The file is stored before its job is queued. If an instance dies in the instant between the two, the video stays `pending` with no job to process it.
- Recovering a crashed worker's job takes up to about 40 seconds (heartbeat expiry plus the check interval).
- Uploading needs no account; it's only rate limited.
