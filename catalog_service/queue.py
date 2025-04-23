import redis
import json
from typing import Dict, Any
import os

class UploadQueue:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)
        self.queue_name = "video_uploads"
        self.processing_queue = "processing_uploads"

    async def add_upload(self, video_data: Dict[str, Any]) -> str:
        """Add a new video upload to the queue"""
        upload_id = f"upload_{len(self.redis.lrange(self.queue_name, 0, -1)) + 1}"
        data = {
            "id": upload_id,
            "status": "pending",
            "data": video_data
        }
        self.redis.rpush(self.queue_name, json.dumps(data))
        return upload_id

    async def get_next_upload(self) -> Dict[str, Any]:
        """Get the next video upload to process"""
        # Move from main queue to processing queue
        data = self.redis.blpop(self.queue_name, timeout=0)
        if data:
            upload_data = json.loads(data[1])
            self.redis.rpush(self.processing_queue, data[1])
            return upload_data
        return None

    async def update_status(self, upload_id: str, status: str, metadata: Dict[str, Any] = None):
        """Update the status of an upload"""
        # Find the upload in processing queue
        items = self.redis.lrange(self.processing_queue, 0, -1)
        for item in items:
            data = json.loads(item)
            if data["id"] == upload_id:
                data["status"] = status
                if metadata:
                    data["metadata"] = metadata
                # Remove from processing queue
                self.redis.lrem(self.processing_queue, 1, item)
                # Add to completed/failed queue
                if status in ["completed", "failed"]:
                    self.redis.rpush(f"{status}_uploads", json.dumps(data))
                break

    async def get_upload_status(self, upload_id: str) -> Dict[str, Any]:
        """Get the status of an upload"""
        # Check processing queue
        items = self.redis.lrange(self.processing_queue, 0, -1)
        for item in items:
            data = json.loads(item)
            if data["id"] == upload_id:
                return data

        # Check completed queue
        items = self.redis.lrange("completed_uploads", 0, -1)
        for item in items:
            data = json.loads(item)
            if data["id"] == upload_id:
                return data

        # Check failed queue
        items = self.redis.lrange("failed_uploads", 0, -1)
        for item in items:
            data = json.loads(item)
            if data["id"] == upload_id:
                return data

        return None 