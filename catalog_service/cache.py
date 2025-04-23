from sqlalchemy.orm import Session
from models import VideoCache, Video
from typing import Optional, List
import os
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CacheManager:
    def __init__(self, session: Session, cache_threshold: int = 100, cache_ttl: int = 3600):
        self.session = session
        self.cache_threshold = cache_threshold
        self.cache_ttl = cache_ttl
        self.cache_dir = "/app/cache"
        os.makedirs(self.cache_dir, exist_ok=True)

    def update_view_count(self, video_id: int) -> None:
        """Update the view count for a video"""
        cache_entry = self.session.query(VideoCache).filter(
            VideoCache.video_id == video_id
        ).first()

        if not cache_entry:
            cache_entry = VideoCache(video_id=video_id)
            self.session.add(cache_entry)

        cache_entry.views += 1
        cache_entry.last_accessed = datetime.utcnow()
        self.session.commit()

        # Check if video should be cached
        if cache_entry.views >= self.cache_threshold and not cache_entry.is_cached:
            self._cache_video(video_id)

    def _cache_video(self, video_id: int) -> None:
        """Cache a video locally"""
        try:
            video = self.session.query(Video).get(video_id)
            if not video:
                return

            # Create cache entry
            cache_entry = self.session.query(VideoCache).filter(
                VideoCache.video_id == video_id
            ).first()
            
            if not cache_entry:
                cache_entry = VideoCache(video_id=video_id)
                self.session.add(cache_entry)

            # Set cache location
            cache_path = os.path.join(self.cache_dir, f"{video_id}.mp4")
            cache_entry.cache_location = cache_path
            cache_entry.is_cached = True
            self.session.commit()

            # TODO: Implement actual video caching logic
            # This would involve copying the video from MinIO to local cache
            logger.info(f"Cached video {video_id} at {cache_path}")

        except Exception as e:
            logger.error(f"Error caching video {video_id}: {e}")

    def get_cached_video(self, video_id: int) -> Optional[str]:
        """Get the cached location of a video if available"""
        cache_entry = self.session.query(VideoCache).filter(
            VideoCache.video_id == video_id,
            VideoCache.is_cached == True
        ).first()

        if not cache_entry:
            return None

        # Check if cache is still valid
        if datetime.utcnow() - cache_entry.last_accessed > timedelta(seconds=self.cache_ttl):
            cache_entry.is_cached = False
            self.session.commit()
            return None

        return cache_entry.cache_location

    def cleanup_cache(self) -> None:
        """Clean up expired cache entries"""
        expired_time = datetime.utcnow() - timedelta(seconds=self.cache_ttl)
        expired_entries = self.session.query(VideoCache).filter(
            VideoCache.is_cached == True,
            VideoCache.last_accessed < expired_time
        ).all()

        for entry in expired_entries:
            try:
                if os.path.exists(entry.cache_location):
                    os.remove(entry.cache_location)
                entry.is_cached = False
                self.session.commit()
            except Exception as e:
                logger.error(f"Error cleaning up cache for video {entry.video_id}: {e}")

    def get_popular_videos(self, limit: int = 10) -> List[Video]:
        """Get the most popular videos"""
        return self.session.query(Video).join(VideoCache).filter(
            VideoCache.views >= self.cache_threshold
        ).order_by(VideoCache.views.desc()).limit(limit).all() 