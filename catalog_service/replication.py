from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from models import Base, ReplicationLog, Video
import json
import os
from typing import List, Dict, Any
import asyncio
import aiohttp
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ReplicationManager:
    def __init__(self, db_url: str, node_id: str, other_nodes: List[str]):
        self.engine = create_engine(db_url)
        self.node_id = node_id
        self.other_nodes = other_nodes
        self.session = Session(self.engine)
        self.replication_interval = 5  # seconds

    async def start_replication(self):
        """Start the replication process"""
        while True:
            try:
                await self.replicate_changes()
            except Exception as e:
                logger.error(f"Replication error: {e}")
            await asyncio.sleep(self.replication_interval)

    async def replicate_changes(self):
        """Replicate changes to other nodes"""
        # Get pending changes
        pending_changes = self.session.query(ReplicationLog).filter(
            ReplicationLog.status == "pending",
            ReplicationLog.source_node != self.node_id
        ).all()

        for change in pending_changes:
            try:
                # Apply the change locally
                await self.apply_change(change)
                
                # Mark as completed
                change.status = "completed"
                self.session.commit()
            except Exception as e:
                logger.error(f"Error applying change {change.id}: {e}")
                change.status = "failed"
                self.session.commit()

    async def apply_change(self, change: ReplicationLog):
        """Apply a replication change"""
        data = json.loads(change.data)
        
        if change.operation == "create":
            video = Video(**data)
            self.session.add(video)
        elif change.operation == "update":
            video = self.session.query(Video).get(change.record_id)
            if video:
                for key, value in data.items():
                    setattr(video, key, value)
        elif change.operation == "delete":
            video = self.session.query(Video).get(change.record_id)
            if video:
                video.is_deleted = True

        self.session.commit()

    async def broadcast_change(self, operation: str, table_name: str, record_id: int, data: Dict[str, Any]):
        """Broadcast a change to other nodes"""
        change = ReplicationLog(
            operation=operation,
            table_name=table_name,
            record_id=record_id,
            data=json.dumps(data),
            source_node=self.node_id
        )
        self.session.add(change)
        self.session.commit()

        # Broadcast to other nodes
        async with aiohttp.ClientSession() as session:
            for node in self.other_nodes:
                try:
                    await session.post(
                        f"http://{node}/replicate",
                        json={
                            "operation": operation,
                            "table_name": table_name,
                            "record_id": record_id,
                            "data": data,
                            "source_node": self.node_id
                        }
                    )
                except Exception as e:
                    logger.error(f"Error broadcasting to {node}: {e}")

    def get_node_status(self) -> Dict[str, Any]:
        """Get the status of all nodes"""
        status = {
            "node_id": self.node_id,
            "pending_changes": self.session.query(ReplicationLog).filter(
                ReplicationLog.status == "pending"
            ).count(),
            "total_changes": self.session.query(ReplicationLog).count(),
            "last_sync": self.session.query(ReplicationLog).order_by(
                ReplicationLog.timestamp.desc()
            ).first().timestamp if self.session.query(ReplicationLog).count() > 0 else None
        }
        return status 