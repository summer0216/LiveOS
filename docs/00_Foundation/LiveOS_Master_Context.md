# LiveOS_Master_Context.md

**Project:** LiveOS

**Document Type:** Master Context (Project Bootstrap)

**Version:** 1.0

**Status:** Frozen

**Last Updated:** 2026-07-10

---

# Purpose

This is the single entry point for the LiveOS project.

Every new AI session must read this document first.

Its purpose is to restore the complete project context without requiring the full project history.

This document defines:

* Project Vision
* Current Status
* Frozen Architecture
* Current Sprint
* Next Deliverables
* Project Rules
* Reference Documents

If any document conflicts with this file, follow:

**Architecture Decisions → Master Context → PRD → Prototype → Design System**

---

# Project Overview

**Project Name**

LiveOS

**Product Category**

AI Native Living Operating System

**Mission**

Help people make better living decisions with AI.

The first MVP focuses on apartment rental decisions.

Future scenarios may include:

* City Selection
* School Selection
* Career Decisions
* Healthcare Decisions
* Personal Finance

---

# Current Project Phase

Current Phase

Foundation Sprint

Project Status

Architecture Frozen

Prototype Frozen

Design System Frozen

Development Not Started

---

# Milestone Status

| Milestone          | Status     |
| ------------------ | ---------- |
| Vision             | ✅ Complete |
| PRD v3.0           | ✅ Complete |
| Architecture v1.0  | ✅ Frozen   |
| Prototype v1.0     | ✅ Frozen   |
| Design System v1.0 | ✅ Frozen   |
| Design Tokens      | ⏳ Next     |
| Component Library  | ⏳ Pending  |
| Figma System       | ⏳ Pending  |
| Frontend           | ⏳ Pending  |
| Backend            | ⏳ Pending  |
| AI Integration     | ⏳ Pending  |

---

# Architecture Status

Architecture Version

v1.0 (Frozen)

Architecture changes are NOT allowed during MVP unless approved through an Architecture Change Proposal (ACP).

---

# Product Architecture

```
LiveOS

AI Entry

↓

AI Workspace

├── Conversation

├── Living Profile

├── Property Workspace

├── AI Property Analysis

├── AI Comparison

└── AI Decision

↓

Decision Memory

↓

Settings
```

---

# Core Business Objects

The entire MVP revolves around four objects.

```
Conversation

↓

Living Profile

↓

Property

↓

Decision
```

Everything in the product should be built around these objects.

Never redesign the product around pages.

---

# Primary User Journey

```
AI Entry

↓

Conversation

↓

Living Profile

↓

Property Intake

↓

Property Analysis

↓

Comparison

↓

Decision

↓

Memory
```

This is the only MVP decision pipeline.

---

# Design Principles

Always follow these principles.

1. AI First
2. Conversation First
3. Objects over Pages
4. Explain Every Recommendation
5. Progressive Disclosure
6. Human in Control
7. Calm Interface
8. Consistency Before Creativity

---

# Design Language

Keywords

* Calm
* Minimal
* Intelligent
* Trustworthy
* Warm
* Focused

Avoid

* Dashboard Style
* Gaming Style
* Over Decoration
* Visual Noise

---

# Technical Direction

Frontend

* Next.js
* React
* TypeScript
* Tailwind CSS
* Framer Motion

Backend

* FastAPI

Database

* PostgreSQL
* pgvector

AI

* OpenAI Compatible API

Deployment

* Docker
* Vercel (Frontend)
* Cloud Deployment (Backend)

---

# Current Sprint

Foundation Sprint

Sprint Goal

Build a stable engineering foundation before implementation.

Current Task

LiveOS_Design_Tokens_v1.0

Next Tasks

1. Component Library
2. Figma System
3. Frontend Architecture
4. Backend Architecture
5. AI Architecture

---

# Frozen Documents

The following documents are considered stable.

* LiveOS_Architecture_Decisions.md
* LiveOS_PRD_v3.0_Final.docx
* LiveOS_Project_Context_v1.0.md
* LiveOS_Prototype_Spec_v1.0.md
* LiveOS_Design_System_v1.0.md
* LiveOS_Development_Context_v1.0.md

Do not rewrite these documents unless explicitly requested.

---

# Working Rules

Always continue from the current project state.

Do not restart product discovery.

Do not redesign MVP architecture.

Do not replace existing concepts without approval.

Prioritize implementation over expansion.

Prefer improving existing artifacts instead of creating parallel versions.

---

# Decision Priority

When conflicts occur, use the following order.

1. Architecture Decisions
2. Master Context
3. PRD
4. Prototype Specification
5. Design System
6. Development Context

---

# Naming Convention

Product

LiveOS

Workspace

AI Workspace

Profile

Living Profile

Analysis

AI Property Analysis

Comparison

AI Comparison Workspace

Decision

AI Decision

Memory

Decision Memory

---

# Definition of Success

The MVP is successful when a user can:

* Talk naturally with AI.
* Build a Living Profile automatically.
* Import multiple properties.
* Understand AI analysis.
* Compare candidates.
* Receive an explainable recommendation.
* Save the final decision.

---

# AI Session Instructions

When starting a new AI session:

1. Read this document first.
2. Assume the architecture is frozen.
3. Continue from the current sprint.
4. Never restart the project definition.
5. Focus on the next unfinished deliverable.

---

# End of Master Context
