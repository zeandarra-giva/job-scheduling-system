# Distributed Job Scheduling System for Web Scraping

A production-ready distributed job scheduling and processing system that handles asynchronous article scraping with deduplication, priority queues, and real-time updates.

## Table of Contents
- [Architecture Overview](#architecture-overview)
- [Features](#features)
- [Database Design](#database-design)
- [API Documentation](#api-documentation)
- [Setup Instructions](#setup-instructions)
- [Usage Examples](#usage-examples)
- [Innovative Feature](#innovative-feature)
- [Testing](#testing)
- [Project Structure](#project-structure)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CLIENT APPLICATION                                 │
│                    (Web App, Mobile App, CLI, etc.)                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ HTTP/WebSocket
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API SERVICE                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │   FastAPI App   │  │   Publisher     │  │   WebSocket Handler         │  │
│  │                 │  │   Service       │  │   (Real-time Updates)       │  │
│  │ POST /jobs/sub  │  │                 │  │                             │  │
│  │ GET  /jobs/:id  │  │ - Deduplication │  │ - Subscribe to job updates  │  │
│  │ DEL  /jobs/:id  │  │ - Queue Tasks   │  │ - Broadcast progress        │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
           │                     │                        │
           │                     │                        │
           ▼                     ▼                        ▼
┌───────────────────┐  ┌───────────────────┐  ┌───────────────────────────────┐
│     MongoDB       │  │      Redis        │  │     Redis Pub/Sub             │
│                   │  │                   │  │                               │
│ ┌───────────────┐ │  │ ┌───────────────┐ │  │  ┌─────────────────────────┐  │
│ │    Jobs       │ │  │ │  High Queue   │ │  │  │   job_updates channel  │  │
│ │  Collection   │ │  │ │  (Priority 1-3)│ │  │  │                       │  │
│ └───────────────┘ │  │ └───────────────┘ │  │  │   ← Consumer publishes │  │
│                   │  │ ┌───────────────┐ │  │  │   → WebSocket listens  │  │
│ ┌───────────────┐ │  │ │ Medium Queue  │ │  │  └─────────────────────────┘  │
│ │   Articles    │ │  │ │  (Priority 4-7)│ │  │                               │
│ │  Collection   │ │  │ └───────────────┘ │  │                               │
│ └───────────────┘ │  │ ┌───────────────┐ │  │                               │
│                   │  │ │   Low Queue   │ │  │                               │
│                   │  │ │  (Priority 8-10)│ │  │                               │
│                   │  │ └───────────────┘ │  │                               │
└───────────────────┘  └───────────────────┘  └───────────────────────────────┘
                                │
                                │ RPOP (priority order)
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CONSUMER SERVICE (×3)                                │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         Scraping Worker                               │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │ Poll Queue  │→ │   Scrape    │→ │   Store     │→ │   Update    │  │   │
│  │  │ (Priority)  │  │   Article   │  │   Content   │  │   Job       │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │   │
│  │                                                            │          │   │
│  │                    ┌──────────────────────────────────────┘          │   │
│  │                    │ (On failure: retry with exponential backoff)    │   │
│  │                    ▼                                                  │   │
│  │              ┌─────────────┐                                          │   │
│  │              │  Re-queue   │ (max 3 retries)                          │   │
│  │              │   Task      │                                          │   │
│  │              └─────────────┘                                          │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Job Submission**: Client submits articles via `POST /jobs/submit`
2. **Deduplication**: System checks for existing scraped articles
3. **Queue Publishing**: New articles are pushed to priority queues in Redis
4. **Consumer Processing**: Workers poll queues and scrape articles
5. **Result Storage**: Scraped content stored in MongoDB
6. **Real-time Updates**: Progress published via Redis Pub/Sub to WebSocket clients
7. **Result Retrieval**: Client polls status or retrieves results

---

## Features

### Core Features
- RESTful API for job submission, status tracking, and result retrieval
- Article deduplication (reuses already-scraped content)
- Asynchronous processing via Redis queues
- MongoDB storage for jobs and articles
- Retry logic with exponential backoff (max 3 attempts)
- Job cancellation support
- Dockerized deployment

### Innovative Features
- **Priority Queues**: Articles processed by priority (high/medium/low)
- **Real-time WebSocket Updates**: Subscribe to job progress in real-time
- **Scalable Consumers**: Multiple worker instances for parallel processing

---

## Database Design

### Entity Relationship Diagram

```
┌─────────────────────────────────────────┐      ┌─────────────────────────────────────────┐
│                 JOBS                     │      │               ARTICLES                   │
├─────────────────────────────────────────┤      ├─────────────────────────────────────────┤
│ _id: String (PK)                        │      │ _id: String (PK)                        │
│ status: Enum                            │      │ url: String (Unique Index)              │
│   - PENDING                             │      │ source: String                          │
│   - IN_PROGRESS                         │      │ category: String                        │
│   - COMPLETED                           │      │ priority: Integer                       │
│   - FAILED                              │      │ title: String (nullable)                │
│   - CANCELLED                           │      │ content: String (nullable)              │
│ total_articles: Integer                 │      │ status: Enum                            │
│ new_articles: Integer                   │      │   - PENDING                             │
│ cached_articles: Integer                │      │   - SCRAPING                            │
│ completed_count: Integer                │◄─────│   - SCRAPED                             │
│ failed_count: Integer                   │      │   - FAILED                              │
│ article_ids: Array[String] ─────────────┼──────► error_message: String (nullable)       │
│ created_at: DateTime                    │      │ scraped_at: DateTime (nullable)         │
│ updated_at: DateTime                    │      │ created_at: DateTime                    │
│ completed_at: DateTime (nullable)       │      │ updated_at: DateTime                    │
└─────────────────────────────────────────┘      │ reference_count: Integer                │
                                                 │ retry_count: Integer                    │
                                                 └─────────────────────────────────────────┘
```

### Relationships
- **One Job → Many Articles**: Jobs reference articles via `article_ids` array
- **Many Jobs → One Article**: Articles can be reused across multiple jobs (tracked by `reference_count`)

---

## API Documentation

Access the interactive Swagger UI at: `http://localhost:8000/docs`

### Endpoints

#### POST /jobs/submit
Submit a new scraping job.

**Request:**
```json
{
  "articles": [
    {
      "url": "https://example.com/article1",
      "source": "TechNews",
      "category": "AI",
      "priority": 1
    },
    {
      "url": "https://example.com/article2",
      "source": "TechNews",
      "category": "ML",
      "priority": 2
    }
  ]
}
```

**Response (201 Created):**
```json
{
  "job_id": "job_a1b2c3d4e5f6",
  "status": "IN_PROGRESS",
  "total_articles": 2,
  "new_articles": 2,
  "cached_articles": 0,
  "message": "Job submitted successfully"
}
```

**Error Responses:**
- `422 Unprocessable Entity`: Invalid URL format or duplicate URLs in request

---

#### GET /jobs/{job_id}/status
Get the current status of a job.

**Response (200 OK):**
```json
{
  "job_id": "job_a1b2c3d4e5f6",
  "status": "IN_PROGRESS",
  "total_articles": 10,
  "completed": 7,
  "failed": 1,
  "pending": 2,
  "created_at": "2024-02-04T10:30:00Z",
  "updated_at": "2024-02-04T10:35:00Z"
}
```

**Error Responses:**
- `404 Not Found`: Job does not exist

---

#### GET /jobs/{job_id}/results
Get the complete results of a job including scraped content.

**Response (200 OK):**
```json
{
  "job_id": "job_a1b2c3d4e5f6",
  "status": "COMPLETED",
  "total_articles": 10,
  "successful": 9,
  "failed": 1,
  "results": [
    {
      "article_id": "art_001",
      "url": "https://example.com/article1",
      "source": "TechNews",
      "category": "AI",
      "title": "Understanding Large Language Models",
      "content": "Full scraped article content here...",
      "scraped_at": "2024-02-04T10:32:00Z",
      "cached": false
    },
    {
      "article_id": "art_002",
      "url": "https://example.com/article2",
      "source": "TechNews",
      "category": "ML",
      "title": "Deep Learning Fundamentals",
      "content": "Full scraped article content here...",
      "scraped_at": "2024-02-01T08:15:00Z",
      "cached": true
    }
  ],
  "failed_articles": [
    {
      "url": "https://example.com/article5",
      "error": "404 Not Found",
      "attempted_at": "2024-02-04T10:33:00Z"
    }
  ]
}
```

---

#### DELETE /jobs/{job_id}
Cancel a pending or in-progress job.

**Response (200 OK):**
```json
{
  "job_id": "job_a1b2c3d4e5f6",
  "status": "CANCELLED",
  "message": "Job cancelled. Removed 5 pending tasks."
}
```

**Error Responses:**
- `404 Not Found`: Job does not exist
- `400 Bad Request`: Job already completed or failed

---

#### GET /jobs/
List all jobs with optional filtering.

**Query Parameters:**
- `status_filter` (optional): Filter by status (PENDING, IN_PROGRESS, COMPLETED, FAILED, CANCELLED)
- `limit` (optional): Max results (default 50)
- `skip` (optional): Skip results for pagination

---

#### WebSocket /ws
Subscribe to all job updates in real-time.

#### WebSocket /ws/jobs/{job_id}
Subscribe to updates for a specific job.

**Message Format:**
```json
{
  "type": "job_update",
  "job_id": "job_a1b2c3d4e5f6",
  "article_id": "art_001",
  "status": "IN_PROGRESS",
  "completed": 5,
  "failed": 0,
  "total": 10
}
```

---

## Setup Instructions

### Prerequisites
- Docker and Docker Compose installed
- Git

### Quick Start

```bash
# Clone the repository
git clone <repository-url>
cd job-scheduling-system

# Copy environment file
cp .env.example .env

# Build and start all services
docker-compose up --build

# The API will be available at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

### Scaling Consumers

```bash
# Scale to 5 consumer instances
docker-compose up --scale consumer=5

# Scale with build
docker-compose up --build --scale consumer=5
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f consumer
docker-compose logs -f api
```

### Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Start MongoDB and Redis (using Docker)
docker-compose up -d mongodb redis

# Run API
PYTHONPATH=. python -m uvicorn api.main:app --reload

# Run Consumer (in separate terminal)
PYTHONPATH=. python -m consumer.consumer
```

---

## Usage Examples

### Submit a Job

```bash
curl -X POST http://localhost:8000/jobs/submit \
  -H "Content-Type: application/json" \
  -d '{
    "articles": [
      {
        "url": "https://www.bbc.com/news/technology",
        "source": "BBC",
        "category": "Technology",
        "priority": 1
      },
      {
        "url": "https://techcrunch.com/",
        "source": "TechCrunch",
        "category": "Tech News",
        "priority": 2
      }
    ]
  }'
```

### Check Job Status

```bash
curl http://localhost:8000/jobs/job_a1b2c3d4e5f6/status
```

### Get Job Results

```bash
curl http://localhost:8000/jobs/job_a1b2c3d4e5f6/results
```

### Cancel a Job

```bash
curl -X DELETE http://localhost:8000/jobs/job_a1b2c3d4e5f6
```

### List All Jobs

```bash
curl "http://localhost:8000/jobs/?status_filter=COMPLETED&limit=10"
```

### WebSocket Connection (JavaScript)

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/jobs/job_a1b2c3d4e5f6');

ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  console.log('Job update:', update);

  if (update.status === 'COMPLETED') {
    console.log('Job completed!');
    ws.close();
  }
};

ws.onopen = () => {
  console.log('Connected to job updates');
};
```

### Using Sample Data

```bash
curl -X POST http://localhost:8000/jobs/submit \
  -H "Content-Type: application/json" \
  -d @sample_articles.json
```

---

## Innovative Feature

### Priority Queues with Real-time WebSocket Updates

This implementation includes two innovative features that work together:

#### 1. Priority Queues

**Problem Solved:** Not all articles have equal importance. Some need to be scraped urgently while others can wait.

**Technical Implementation:**
- Articles are assigned a priority level (1-10, lower = higher priority)
- Three Redis queues: `high` (1-3), `medium` (4-7), `low` (8-10)
- Consumers poll queues in priority order (high -> medium -> low)
- Retried tasks are placed in high-priority queue for faster resolution

**Usage:**
```json
{
  "articles": [
    {"url": "...", "priority": 1},  // Processed first
    {"url": "...", "priority": 5},  // Processed after high priority
    {"url": "...", "priority": 9}   // Processed last
  ]
}
```

#### 2. Real-time WebSocket Updates

**Problem Solved:** Polling for status is inefficient. Clients need instant feedback on job progress.

**Technical Implementation:**
- Redis Pub/Sub channel for job updates
- WebSocket endpoints for subscribing to updates
- Consumers publish progress after each article
- Supports both job-specific and broadcast subscriptions

**Value Proposition:**
- Reduced API load (no constant polling)
- Instant feedback for better UX
- Efficient resource utilization

---

## Testing

### Run Tests

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
PYTHONPATH=. pytest tests/ -v

# Run specific test file
PYTHONPATH=. pytest tests/test_scraper.py -v

# Run with coverage
PYTHONPATH=. pytest tests/ --cov=. --cov-report=html
```

### Test Categories

1. **Unit Tests** (`test_scraper.py`): Scraper logic and HTML parsing
2. **Integration Tests** (`test_api.py`): API endpoint testing
3. **Service Tests** (`test_deduplication.py`): Deduplication logic

### Sample Test Data

The `sample_articles.json` file contains 10 real article URLs for testing:
- BBC News Technology
- TechCrunch
- Wired
- Ars Technica
- The Verge
- And more...

---

## Project Structure

```
job-scheduling-system/
├── api/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry point
│   ├── websocket.py         # WebSocket handler
│   ├── routes/
│   │   ├── __init__.py
│   │   └── jobs.py          # Job endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   ├── publisher.py     # Redis queue publishing
│   │   └── deduplication.py # Article deduplication logic
│   ├── models/
│   │   ├── __init__.py
│   │   ├── job.py           # Job model
│   │   └── article.py       # Article model
│   └── schemas/
│       ├── __init__.py
│       ├── requests.py      # Request Pydantic schemas
│       └── responses.py     # Response Pydantic schemas
├── consumer/
│   ├── __init__.py
│   ├── consumer.py          # Consumer entry point
│   ├── scraper.py           # Web scraping logic
│   └── worker.py            # Worker process
├── database/
│   ├── __init__.py
│   ├── connection.py        # DB connection setup
│   └── repositories/
│       ├── __init__.py
│       ├── job_repo.py      # Job CRUD operations
│       └── article_repo.py  # Article CRUD operations
├── shared/
│   ├── __init__.py
│   ├── config.py            # Shared configuration
│   └── utils.py             # Utility functions
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Pytest fixtures
│   ├── test_api.py          # API tests
│   ├── test_scraper.py      # Scraper tests
│   └── test_deduplication.py # Deduplication tests
├── docker-compose.yml       # Docker Compose config
├── Dockerfile.api           # API service Dockerfile
├── Dockerfile.consumer      # Consumer service Dockerfile
├── requirements.txt         # Python dependencies
├── sample_articles.json     # Sample input data
├── .env.example             # Environment variables template
└── README.md                # This file
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379` |
| `MONGO_URL` | MongoDB connection URL | `mongodb://localhost:27017` |
| `MONGO_DB_NAME` | MongoDB database name | `job_scheduler` |
| `API_PORT` | API server port | `8000` |
| `MAX_RETRY_ATTEMPTS` | Max scraping retries | `3` |
| `SCRAPE_TIMEOUT` | Scraping timeout (seconds) | `30` |

---

## License

MIT License
