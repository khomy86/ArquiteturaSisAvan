import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ualflix:ualflix@localhost:5432/ualflix")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
VIDEO_BUCKET = "videos"
THUMBNAIL_BUCKET = "thumbnails"

# Every catalog instance must share the same secret, otherwise a token issued
# by one instance is rejected by the other.
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))

# The admin account is created (or its password reset) on startup from these.
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

# Set when the service is mounted under a prefix by the reverse proxy, so that
# the generated OpenAPI docs point at the right URLs.
ROOT_PATH = os.getenv("ROOT_PATH", "")
