# LiveOS_Backend_Architecture_v1.0.md

**Project:** LiveOS

**Document Type:** Backend Architecture

**Version:** 1.0

**Status:** Frozen (Foundation)

**Last Updated:** 2026-07-10

---

# 1. Purpose

This document defines the backend architecture for LiveOS MVP.

It establishes:

* System architecture
* Service boundaries
* Domain organization
* AI workflow
* Data persistence
* Security
* Scalability

The backend is designed around AI-native workflows rather than traditional CRUD applications.

---

# 2. Architecture Principles

The backend follows these principles:

1. Domain-driven design
2. API-first
3. AI-first
4. Stateless services
5. Event-ready
6. Explainable decisions
7. Clear separation of concerns

---

# 3. Technology Stack

## Runtime

* Python 3.13+

## Framework

* FastAPI

## Validation

* Pydantic v2

## ORM

* SQLAlchemy 2.x

## Database

* PostgreSQL

## Vector Database

* pgvector

## Cache

* Redis

## Background Jobs

* Celery (or Dramatiq for lightweight deployments)

## Object Storage

* S3-compatible storage (MinIO for local development)

## Observability

* OpenTelemetry
* Prometheus
* Grafana

---

# 4. High-Level Architecture

```text
                    Next.js Frontend
                            │
                     REST / Streaming
                            │
                     FastAPI Gateway
                            │
      ┌──────────────┬──────────────┬──────────────┐
      │              │              │              │
Conversation     Property      Decision      Memory
   Domain          Domain        Domain       Domain
      │              │              │              │
      └──────────────┴──────┬───────┴──────────────┘
                             │
                       AI Orchestrator
                             │
                     LLM / Embedding API
                             │
                  PostgreSQL + pgvector + Redis
```

---

# 5. Domain Modules

The backend is organized by business domains.

```text
app/

conversation/
living_profile/
property/
decision/
memory/
auth/
shared/
```

Each domain owns:

* Models
* Schemas
* Services
* Repositories
* API
* Tests

---

# 6. Project Structure

```text
app/

api/
core/
domains/
services/
repositories/
schemas/
models/
workers/
prompts/
memory/
events/
utils/
tests/
```

No business logic should exist in route handlers.

---

# 7. Layered Architecture

```text
API Layer

↓

Application Layer

↓

Domain Layer

↓

Repository Layer

↓

Database
```

Responsibilities:

* API: request/response only
* Application: use cases
* Domain: business rules
* Repository: persistence
* Database: storage

---

# 8. AI Orchestrator

The AI Orchestrator coordinates all AI workflows.

Responsibilities:

* Prompt construction
* Context aggregation
* Tool invocation
* Response validation
* Confidence calculation
* Decision explanation

The frontend never communicates directly with an LLM.

AI Orchestrator is the Single AI Runtime and internally coordinates Conversation/Profile/Property/Decision/Memory Logical Agents.

---

# 9. Domain Services

## Conversation

Responsibilities:

* Session lifecycle
* Message persistence
* Streaming coordination

---

## Living Profile

Responsibilities:

* Preference extraction
* Confidence scoring
* Profile updates

---

## Property

Responsibilities:

* Property ingestion
* Metadata normalization
* Analysis requests

---

## Decision

Responsibilities:

* Recommendation generation
* Trade-off evaluation
* Alternative generation

---

## Memory

Responsibilities:

* Timeline
* Semantic retrieval
* Long-term context

---

# 10. Repository Pattern

Repositories isolate persistence.

Example:

```text
PropertyRepository

ConversationRepository

DecisionRepository
```

Services never access SQL directly.

---

# 11. AI Prompt Layer

Prompt templates are versioned.

```text
prompts/

conversation/

analysis/

decision/

profile/
```

Prompt changes must be traceable.

---

# 12. Streaming

Server-Sent Events (SSE) is the default transport.

Streaming stages:

```text
Receive Request

↓

Prompt Assembly

↓

LLM Response

↓

Token Stream

↓

Persistence

↓

Profile Update

↓

Complete
```

---

# 13. Background Tasks

Background workers process:

* Embeddings
* Property analysis
* Vector indexing
* Report generation
* Notifications

Long-running jobs must not block HTTP requests.

---

# 14. Persistence

Primary Database

* PostgreSQL

Vector Storage

* pgvector

Cache

* Redis

File Storage

* S3-compatible object storage

---

# 15. Security

Authentication

* JWT

Authorization

* Role-based access control (RBAC)

Security practices:

* HTTPS
* Input validation
* Output sanitization
* Secret management
* Audit logging

---

# 16. Configuration

Environment-based configuration.

Example:

```text
DATABASE_URL

REDIS_URL

OPENAI_API_KEY

OPENAI_BASE_URL

JWT_SECRET

S3_ENDPOINT

LOG_LEVEL
```

Secrets must never be committed to source control.

---

# 17. Logging & Observability

Every request should include:

* Request ID
* User ID (when authenticated)
* Conversation ID
* Duration
* AI provider
* Token usage

Expose metrics for latency, error rate, and throughput.

---

# 18. Error Handling

Standard categories:

* Validation
* Authentication
* Authorization
* Resource
* AI
* Infrastructure

Errors must return stable machine-readable codes.

---

# 19. Testing Strategy

Unit Tests

* Domain services
* Repositories
* Utilities

Integration Tests

* API endpoints
* Database

AI Tests

* Prompt regression
* Structured output validation

End-to-End Tests

* Complete user journeys

---

# 20. Deployment

Containerized deployment using Docker.

Recommended services:

* FastAPI
* PostgreSQL
* Redis
* MinIO
* Worker
* Reverse Proxy

Production orchestration:

* Docker Compose (MVP)
* Kubernetes (Future)

---

# 21. Scalability Roadmap

MVP

* Modular monolith

Phase 2

* Extract AI Worker
* Extract Search Service

Phase 3

* Event-driven architecture
* Independent domain services

Avoid premature microservices.

---

# 22. Backend Governance

Rules:

1. Domain owns its business logic.
2. Route handlers remain thin.
3. Repositories own persistence.
4. AI orchestration is centralized.
5. Shared utilities must remain framework-agnostic.
6. Every feature requires automated tests.
7. Architecture changes require an Architecture Decision Record (ADR).

---

# End of Document
