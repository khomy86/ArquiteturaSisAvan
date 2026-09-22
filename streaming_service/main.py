import logging
import os
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.responses import StreamingResponse
from minio import Minio
from minio.error import S3Error

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("streaming_service")

BUCKET = "videos"
CHUNK_SIZE = 256 * 1024

minio_client = Minio(
    os.getenv("MINIO_ENDPOINT", "localhost:9000"),
    access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
    secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
    secure=False,
)

app = FastAPI(title="UALFlix Streaming Service")


class RangeNotSatisfiable(Exception):
    pass


def parse_range(header: str | None, size: int) -> tuple[int, int] | None:
    """Parse a `Range: bytes=...` header into an inclusive (start, end) pair.

    Returns None when the whole file should be sent: no header, a unit other
    than bytes, a malformed value, or a multi-range request (which we don't
    support, and RFC 9110 lets us answer with the full body instead).
    """
    if not header:
        return None
    unit, _, spec = header.partition("=")
    if unit.strip().lower() != "bytes" or "," in spec:
        return None

    first, sep, last = spec.strip().partition("-")
    if not sep:
        return None
    try:
        if first == "":
            # Suffix range, e.g. "bytes=-500" means the last 500 bytes.
            length = int(last)
            if length <= 0:
                raise RangeNotSatisfiable
            return max(size - length, 0), size - 1
        start = int(first)
        end = int(last) if last else size - 1
    except ValueError:
        return None

    if start >= size:
        raise RangeNotSatisfiable
    if end < start:
        return None
    return start, min(end, size - 1)


def _iter_object(response):
    try:
        yield from response.stream(CHUNK_SIZE)
    finally:
        response.close()
        response.release_conn()


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}


@app.get("/stream/{video_id}")
def stream_video(video_id: int, range_header: Annotated[str | None, Header(alias="range")] = None):
    object_name = str(video_id)
    try:
        stat = minio_client.stat_object(bucket_name=BUCKET, object_name=object_name)
    except S3Error as exc:
        if exc.code in ("NoSuchKey", "NoSuchObject"):
            raise HTTPException(status_code=404, detail="Video not found")
        raise

    size = stat.size
    try:
        byte_range = parse_range(range_header, size)
    except RangeNotSatisfiable:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})

    start, end = byte_range or (0, size - 1)
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(end - start + 1),
    }
    if byte_range:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"

    obj = minio_client.get_object(
        bucket_name=BUCKET, object_name=object_name, offset=start, length=end - start + 1
    )
    return StreamingResponse(
        _iter_object(obj),
        status_code=206 if byte_range else 200,
        media_type=stat.content_type or "video/mp4",
        headers=headers,
    )
