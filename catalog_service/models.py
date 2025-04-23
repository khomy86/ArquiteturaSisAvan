from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import uuid

Base = declarative_base()

class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(String)
    duration = Column(Float)  # in seconds
    url = Column(String, nullable=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    node_id = Column(String)  # For replication tracking
    version = Column(Integer, default=1)  # For optimistic locking
    is_deleted = Column(Boolean, default=False)

class VideoCache(Base):
    __tablename__ = "video_cache"

    id = Column(Integer, primary_key=True)
    video_id = Column(Integer, nullable=False)
    views = Column(Integer, default=0)
    last_accessed = Column(DateTime(timezone=True), server_default=func.now())
    is_cached = Column(Boolean, default=False)
    cache_location = Column(String)  # URL or path to cached content

class ReplicationLog(Base):
    __tablename__ = "replication_log"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    operation = Column(String, nullable=False)  # 'create', 'update', 'delete'
    table_name = Column(String, nullable=False)
    record_id = Column(Integer, nullable=False)
    data = Column(String)  # JSON string of the record
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    source_node = Column(String, nullable=False)
    status = Column(String, default="pending")  # 'pending', 'completed', 'failed' 