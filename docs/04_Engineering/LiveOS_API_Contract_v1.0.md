# LiveOS_API_Contract_v1.0.md

**Project:** LiveOS

**Document Type:** API Contract

**Version:** 1.0

**Status:** Frozen (Foundation)

**Last Updated:** 2026-07-10

---

# 1. Purpose

This document defines the API contract for LiveOS MVP.

It is the single source of truth for:

* REST APIs
* Streaming APIs
* Request/Response models
* Error handling
* Object schemas
* Versioning

Frontend, Backend and AI services must follow this specification.

---

# 2. Design Principles

All APIs should be:

* Resource-oriented
* Versioned
* Stateless
* Consistent
* Explainable
* AI-friendly

Streaming is the default interaction model.

---

# 3. Base URL

```text
/api/v1
```

Future versions:

```text
/api/v2
```

---

# 4. Authentication

Authorization Header

```http
Authorization: Bearer <token>
```

Future:

* OAuth
* Social Login
* SSO

---

# 5. Response Envelope

Every response follows the same structure.

```json
{
  "success": true,
  "data": {},
  "meta": {},
  "error": null
}
```

Error example:

```json
{
  "success": false,
  "data": null,
  "meta": {},
  "error": {
    "code": "PROPERTY_NOT_FOUND",
    "message": "Property does not exist."
  }
}
```

---

# 6. Standard Error Codes

```text
VALIDATION_ERROR

UNAUTHORIZED

FORBIDDEN

NOT_FOUND

CONFLICT

RATE_LIMITED

AI_TIMEOUT

STREAM_INTERRUPTED

INTERNAL_ERROR
```

Errors should be stable and machine-readable.

---

# 7. Core Resources

The MVP exposes four primary resources.

```text
Conversation

Living Profile

Property

Decision
```

These map directly to the business object model.

---

# 8. Conversation API

## Start Conversation

```http
POST /conversation
```

Response

```json
{
  "conversationId": "conv_001"
}
```

---

## Send Message

```http
POST /conversation/{id}/messages
```

Request

```json
{
  "role": "user",
  "content": "I am looking for a two-bedroom apartment."
}
```

Streaming response via SSE.

---

## Conversation History

```http
GET /conversation/{id}
```

---

# 9. Living Profile API

## Get Profile

```http
GET /profile
```

Response

```json
{
  "profileId": "profile_001",
  "summary": "...",
  "preferences": [],
  "confidence": 0.87
}
```

---

## Update Profile

```http
PATCH /profile
```

Only backend or AI services should perform automatic updates.

---

# 10. Property API

## Create Property

```http
POST /properties
```

Request

```json
{
  "source": "manual",
  "url": "",
  "address": ""
}
```

---

## Property List

```http
GET /properties
```

Supports:

* Pagination
* Filtering
* Sorting

---

## Property Detail

```http
GET /properties/{id}
```

---

## Delete Property

```http
DELETE /properties/{id}
```

---

# 11. Analysis API

Trigger AI analysis.

```http
POST /properties/{id}/analyze
```

Response

```json
{
  "analysisId": "analysis_001",
  "status": "running"
}
```

Progress updates should be streamed.

---

# 12. Comparison API

Compare selected properties.

```http
POST /comparison
```

Request

```json
{
  "propertyIds": [
    "property_001",
    "property_002"
  ]
}
```

---

# 13. Decision API

Generate recommendation.

```http
POST /decision
```

Response

```json
{
  "recommendation": "...",
  "confidence": 0.92,
  "tradeOffs": [],
  "alternatives": []
}
```

---

# 14. Memory API

Decision history.

```http
GET /memory
```

Supports:

* Timeline
* Filtering
* Search

---

# 15. Streaming API

Transport

Server-Sent Events (SSE)

Endpoint

```http
GET /conversation/{id}/stream
```

Events

```text
message.start

message.delta

message.complete

profile.updated

analysis.updated

decision.ready

error
```

Clients should handle reconnects gracefully.

---

# 16. Pagination

Standard format

```json
{
  "page": 1,
  "pageSize": 20,
  "total": 84,
  "items": []
}
```

---

# 17. Object Schemas

## Conversation

```json
{
  "id": "",
  "messages": [],
  "createdAt": "",
  "updatedAt": ""
}
```

## Message

```json
{
  "id": "",
  "role": "user",
  "content": "",
  "timestamp": ""
}
```

## Living Profile

```json
{
  "id": "",
  "summary": "",
  "preferences": [],
  "confidence": 0
}
```

## Property

```json
{
  "id": "",
  "title": "",
  "address": "",
  "price": 0,
  "status": ""
}
```

## Decision

```json
{
  "id": "",
  "recommendation": "",
  "confidence": 0,
  "reasons": [],
  "tradeOffs": [],
  "createdAt": ""
}
```

---

# 18. Validation

Input validation should occur at the API boundary.

Recommended:

* Pydantic (Backend)
* Zod (Frontend)

Schemas should remain aligned.

---

# 19. Versioning

Version through URL.

```text
/api/v1
```

Breaking changes require a new API version.

---

# 20. Security

* HTTPS only
* JWT authentication
* Input validation
* Output sanitization
* Rate limiting
* Audit logging

Sensitive data should never be exposed to the client.

---

# 21. API Governance

Rules

1. Every endpoint must have an owner.
2. Every endpoint must define request and response schemas.
3. Breaking changes require version updates.
4. API changes require documentation updates.
5. Streaming events are versioned alongside REST APIs.

---

# End of Document
