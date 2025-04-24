import redis
import json
from typing import Dict, Any, Optional
import os
import uuid

class UploadQueue:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.queue_name = "video_uploads_queue"
        self.status_key_prefix = "upload_status:"

    async def add_upload(self, video_data: Dict[str, Any]) -> str:
        """Add a new video upload and store its initial status."""
        upload_id = str(uuid.uuid4())
        status_data = {
            "id": upload_id,
            "status": "pending",
            "data": video_data,
            "metadata": None
        }
        status_key = f"{self.status_key_prefix}{upload_id}"
        
        self.redis.set(status_key, json.dumps(status_data))
        
        self.redis.rpush(self.queue_name, upload_id)
        
        return upload_id

    async def get_next_upload_id(self) -> Optional[str]:
        """Get the next upload ID to process from the queue."""
        upload_id = self.redis.lpop(self.queue_name)
        return upload_id

    async def update_status(self, upload_id: str, status: str, metadata: Optional[Dict[str, Any]] = None):
        """Update the status of an upload using its ID key."""
        status_key = f"{self.status_key_prefix}{upload_id}"
        try:
            current_status_str = self.redis.get(status_key)
            if not current_status_str:
                print(f"Warning: Status key {status_key} not found for update.")
                return
                
            status_data = json.loads(current_status_str)
            status_data["status"] = status
            if metadata:
                status_data["metadata"] = metadata
            
            self.redis.set(status_key, json.dumps(status_data))
            
            if status in ["completed", "failed"]:
                 self.redis.expire(status_key, 3600)

        except json.JSONDecodeError:
            print(f"Error decoding JSON for status key {status_key}")
        except Exception as e:
             print(f"Error updating status for {upload_id}: {e}")

    async def get_upload_status(self, upload_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of an upload directly using its ID key."""
        status_key = f"{self.status_key_prefix}{upload_id}"
        status_str = self.redis.get(status_key)
        
        if status_str:
            try:
                return json.loads(status_str)
            except json.JSONDecodeError:
                print(f"Error decoding JSON for status key {status_key}")
                return None
        else:
            return None 