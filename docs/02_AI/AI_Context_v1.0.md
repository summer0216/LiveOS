# LiveOS AI Context v1.0

Version: v1.0

Status: Active

Purpose:
This document is the primary AI context for the LiveOS project.
It provides the minimum project knowledge required for AI assistants
(ChatGPT, Cursor, Claude Code, Gemini, etc.)
to understand the project and continue development consistently.

---

# 1. Project Overview

Project Name

LiveOS

Vision

LiveOS is an AI Native Living Decision System.

Unlike traditional software that helps users complete tasks,
LiveOS helps users make better life decisions through AI understanding,
memory and decision intelligence.

Current MVP focuses on:

Housing Decision Assistance.

---

# 2. Current Project Status

Current Stage

MVP Development

Foundation

✅ Frozen

PRD

✅ Frozen

Prototype

Ready for implementation

Current Goal

Build a working MVP as quickly as possible.

Do not over-engineer.

---

# 3. MVP Scope

Included

- AI Conversation
- Living Profile
- Property Workspace
- AI Decision
- Decision History
- Memory

Not Included

- Marketplace
- Payment
- Transaction
- Social
- Multi-user collaboration
- Microservices

---

# 4. AI Runtime

LiveOS adopts:

Single AI Runtime

Multiple Logical Agents

Logical Agents

- Conversation Agent
- Profile Agent
- Property Agent
- Decision Agent
- Memory Agent

Logical Agents represent business responsibilities only.

They are NOT:

- Independent LLMs
- Independent Processes
- Independent APIs
- Multi-Agent Frameworks

All Logical Agents share:

- One Runtime
- One Context Builder
- One Prompt Pipeline
- One Memory
- One OpenAI Compatible API

Architecture Principle

Single Runtime.
Multiple Logical Agents.

---

# 5. User Journey

AI Entry

↓

Conversation

↓

Living Profile

↓

Property Workspace

↓

Comparison

↓

Decision

↓

Memory

---

# 6. Prototype Screens

S01 AI Entry

S02 Conversation

S03 Living Profile

S04 Property Workspace

S05 Property Detail

S06 Property Comparison

S07 AI Decision

S08 Memory

---

# 7. Tech Stack

Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS
- shadcn/ui

Backend

- FastAPI
- Python

Database

- PostgreSQL

Vector

- pgvector

AI

- OpenAI Compatible API

Deployment

- Docker

---

# 8. Development Principles

Always prioritize:

MVP First

Feature First

Code First

Simple Architecture

Avoid:

- Premature Optimization
- Microservices
- Complex Multi-Agent Systems
- Enterprise-level Infrastructure

If there is a simpler solution,
always choose the simpler one.

---

# 9. Foundation Documents

Project entry:

01_LiveOS_Master_Context.md

Product:

LiveOS_PRD_v3.0_Final_Complete.docx

Prototype:

LiveOS_Prototype_Spec_v1.0.md

Design:

LiveOS_Design_System_v1.0.md

Architecture:

LiveOS_Backend_Architecture.md

LiveOS_AI_Architecture.md

Architecture Decisions:

LiveOS_Architecture_Decisions.md

---

# 10. AI Working Rules

When assisting this project:

- Follow the PRD.
- Follow Architecture Decisions (ADR).
- Keep responses consistent with the Foundation.
- Do not introduce unnecessary complexity.
- Do not redesign the product unless requested.
- Generate production-quality code when implementation is requested.
- Prefer practical MVP solutions over theoretical architecture.

The primary objective is:

Build a usable LiveOS MVP as quickly as possible.