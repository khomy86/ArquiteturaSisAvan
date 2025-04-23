# UALFlix - Distributed Video Streaming System

A distributed video streaming platform built with Python, focusing on distributed systems, clustering, virtualization, and cloud computing.

## System Components

- Catalog Service: Manages video metadata and catalog information
- Streaming Service: Handles video streaming and content delivery
- Web Interface: User-facing web application
- Admin Panel: Content management interface
- Queue System: Asynchronous upload processing
- Monitoring Dashboard: Real-time performance metrics

## Technology Stack

- Python 3.8+
- FastAPI (Backend services)
- React (Frontend)
- Docker & Docker Compose
- Redis (Queue system)
- PostgreSQL (Database)
- MinIO (Object storage)
- Prometheus & Grafana (Monitoring)

## Setup Instructions

1. Clone the repository
2. Install Docker and Docker Compose
3. Run `docker-compose up -d`
4. Access the web interface at `http://localhost:3000`
5. Access the admin panel at `http://localhost:3000/admin`
6. Access the monitoring dashboard at `http://localhost:3000/monitoring`

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run development servers
python -m catalog_service
python -m streaming_service
```

## Project Structure

```
ualflix/
├── catalog_service/      # Video catalog service
├── streaming_service/    # Video streaming service
├── web/                 # Frontend application
├── admin/              # Admin panel
├── monitoring/         # Monitoring and metrics
├── docker/            # Docker configurations
└── tests/             # Test suite
```

## License

MIT License 