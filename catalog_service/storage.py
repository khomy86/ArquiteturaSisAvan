import json

from minio import Minio

from . import config

client = Minio(
    config.MINIO_ENDPOINT,
    access_key=config.MINIO_ACCESS_KEY,
    secret_key=config.MINIO_SECRET_KEY,
    secure=False,
)

# Thumbnails are served straight out of MinIO by nginx, so that bucket needs
# anonymous read access. Videos stay private and go through the streaming service.
_PUBLIC_READ_THUMBNAILS = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"AWS": ["*"]},
        "Action": ["s3:GetObject"],
        "Resource": [f"arn:aws:s3:::{config.THUMBNAIL_BUCKET}/*"],
    }],
})


def video_key(video_id: int) -> str:
    return str(video_id)


def thumbnail_key(video_id: int) -> str:
    return f"{video_id}.jpg"


def thumbnail_url(video_id: int) -> str:
    return f"/{config.THUMBNAIL_BUCKET}/{thumbnail_key(video_id)}"


def ensure_buckets() -> None:
    for bucket in (config.VIDEO_BUCKET, config.THUMBNAIL_BUCKET):
        if not client.bucket_exists(bucket_name=bucket):
            client.make_bucket(bucket_name=bucket)
    client.set_bucket_policy(bucket_name=config.THUMBNAIL_BUCKET, policy=_PUBLIC_READ_THUMBNAILS)


def remove_video_files(video_id: int) -> None:
    client.remove_object(bucket_name=config.VIDEO_BUCKET, object_name=video_key(video_id))
    client.remove_object(bucket_name=config.THUMBNAIL_BUCKET, object_name=thumbnail_key(video_id))
