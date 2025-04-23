import asyncio
import aiohttp
import time
import random
import json
from typing import List, Dict
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LoadTester:
    def __init__(self, base_url: str, num_requests: int = 1000, concurrency: int = 10):
        self.base_url = base_url
        self.num_requests = num_requests
        self.concurrency = concurrency
        self.results: List[Dict] = []
        self.video_ids: List[int] = []

    async def fetch_video_ids(self):
        """Fetch available video IDs for testing"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/videos") as response:
                if response.status == 200:
                    videos = await response.json()
                    self.video_ids = [video["id"] for video in videos]

    async def test_video_streaming(self, session: aiohttp.ClientSession, video_id: int):
        """Test video streaming performance"""
        start_time = time.time()
        try:
            async with session.get(f"{self.base_url}/stream/{video_id}") as response:
                if response.status == 200:
                    # Read first chunk to measure initial response time
                    await response.content.read(1024)
                    end_time = time.time()
                    return {
                        "type": "streaming",
                        "video_id": video_id,
                        "status": response.status,
                        "duration": end_time - start_time,
                        "success": True
                    }
        except Exception as e:
            return {
                "type": "streaming",
                "video_id": video_id,
                "status": 500,
                "duration": time.time() - start_time,
                "success": False,
                "error": str(e)
            }

    async def test_video_list(self, session: aiohttp.ClientSession):
        """Test video list endpoint performance"""
        start_time = time.time()
        try:
            async with session.get(f"{self.base_url}/videos") as response:
                if response.status == 200:
                    await response.json()
                    end_time = time.time()
                    return {
                        "type": "list",
                        "status": response.status,
                        "duration": end_time - start_time,
                        "success": True
                    }
        except Exception as e:
            return {
                "type": "list",
                "status": 500,
                "duration": time.time() - start_time,
                "success": False,
                "error": str(e)
            }

    async def worker(self, session: aiohttp.ClientSession):
        """Worker function for concurrent testing"""
        for _ in range(self.num_requests // self.concurrency):
            # Randomly choose between streaming and list endpoints
            if random.random() < 0.7:  # 70% chance of streaming
                if self.video_ids:
                    video_id = random.choice(self.video_ids)
                    result = await self.test_video_streaming(session, video_id)
                else:
                    result = await self.test_video_list(session)
            else:
                result = await self.test_video_list(session)
            
            self.results.append(result)

    async def run_test(self):
        """Run the load test"""
        await self.fetch_video_ids()
        
        start_time = time.time()
        async with aiohttp.ClientSession() as session:
            tasks = [self.worker(session) for _ in range(self.concurrency)]
            await asyncio.gather(*tasks)
        end_time = time.time()

        self.analyze_results(end_time - start_time)

    def analyze_results(self, total_duration: float):
        """Analyze and report test results"""
        total_requests = len(self.results)
        successful_requests = sum(1 for r in self.results if r["success"])
        streaming_requests = sum(1 for r in self.results if r["type"] == "streaming")
        list_requests = sum(1 for r in self.results if r["type"] == "list")

        streaming_durations = [r["duration"] for r in self.results if r["type"] == "streaming" and r["success"]]
        list_durations = [r["duration"] for r in self.results if r["type"] == "list" and r["success"]]

        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "success_rate": (successful_requests / total_requests) * 100,
            "total_duration": total_duration,
            "requests_per_second": total_requests / total_duration,
            "streaming_requests": {
                "count": streaming_requests,
                "avg_duration": sum(streaming_durations) / len(streaming_durations) if streaming_durations else 0,
                "min_duration": min(streaming_durations) if streaming_durations else 0,
                "max_duration": max(streaming_durations) if streaming_durations else 0
            },
            "list_requests": {
                "count": list_requests,
                "avg_duration": sum(list_durations) / len(list_durations) if list_durations else 0,
                "min_duration": min(list_durations) if list_durations else 0,
                "max_duration": max(list_durations) if list_durations else 0
            }
        }

        # Save report to file
        with open("load_test_report.json", "w") as f:
            json.dump(report, f, indent=2)

        # Print summary
        logger.info(f"Load Test Report:")
        logger.info(f"Total Requests: {total_requests}")
        logger.info(f"Success Rate: {report['success_rate']:.2f}%")
        logger.info(f"Requests per Second: {report['requests_per_second']:.2f}")
        logger.info(f"Average Streaming Duration: {report['streaming_requests']['avg_duration']:.3f}s")
        logger.info(f"Average List Duration: {report['list_requests']['avg_duration']:.3f}s")

if __name__ == "__main__":
    # Example usage
    tester = LoadTester(
        base_url="http://localhost:80",
        num_requests=1000,
        concurrency=10
    )
    asyncio.run(tester.run_test()) 