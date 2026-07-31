# LiveOS Architecture Decisions

**Project:** LiveOS

**Document Type:** Architecture Decision Record (ADR)

**Version:** 1.0

**Status:** Frozen

**Last Updated:** 2026-07-10

---

# Purpose

This document records the long-term architectural decisions that define LiveOS.

Its purpose is to explain:

- Why important decisions were made
- What alternatives were considered
- What constraints those decisions introduce

This document changes infrequently.

Only major architectural changes should be recorded here.

---

# Decision-001

## AI Native First

Status

Accepted

---

### Decision

LiveOS is an AI Native product.

AI is the primary interface.

Traditional UI exists only to support AI interaction.

---

### Reason

Users should interact with an intelligent system instead of navigating complex software.

---

### Consequence

Every feature should begin with AI capability before traditional UI design.

---

# Decision-002

## Conversation is the Primary Interface

Status

Accepted

---

### Decision

Conversation is the main interaction model.

Navigation is secondary.

---

### Reason

Natural language reduces learning cost.

Conversation enables AI understanding.

---

### Consequence

Forms should be minimized.

Users should never be required to manually configure large amounts of information.

---

# Decision-003

## Living Profile is AI Generated

Status

Accepted

---

### Decision

Living Profile is built by AI.

Users review and correct it.

They do not create it manually.

---

### Reason

Behavior is more reliable than questionnaires.

---

### Consequence

Every conversation updates the profile.

Profile becomes long-term memory.

---

# Decision-004

## Objects over Pages

Status

Accepted

---

### Decision

LiveOS is organized around business objects.

Objects:

- Conversation
- Living Profile
- Property
- Decision

Pages visualize objects.

Objects drive the product.

---

### Reason

Object-oriented architecture scales better than page-oriented architecture.

---

### Consequence

Future scenarios (school, job, city, healthcare) can reuse the same object model.

---

# Decision-005

## AI Workspace Layout

Status

Accepted

---

### Decision

Workspace uses a three-column layout.

Navigation

Conversation

Context

---

### Reason

Users need continuous visibility into AI understanding.

---

### Consequence

Living Profile and AI Insights remain visible throughout the decision process.

---

# Decision-006

## Explainable AI

Status

Accepted

---

### Decision

Every recommendation must include:

- Recommendation
- Reasoning
- Confidence
- Trade-offs

---

### Reason

Trust requires transparency.

---

### Consequence

No recommendation should appear without explanation.

---

# Decision-007

## Human Makes the Final Decision

Status

Accepted

---

### Decision

AI recommends.

Users decide.

---

### Reason

LiveOS assists decision-making.

It does not replace human judgment.

---

### Consequence

Every recommendation supports user confirmation, comparison or revision.

---

# Decision-008

## Memory is a Product Capability

Status

Accepted

---

### Decision

Memory is part of the product.

Not an implementation detail.

---

### Reason

Long-term understanding differentiates LiveOS from traditional chatbots.

---

### Consequence

Conversation history, profile evolution and decision history are first-class product assets.

---

# Decision-009

## Foundation Driven Development

Status

Accepted

---

### Decision

Development follows this order:

Design Tokens

↓

Components

↓

Patterns

↓

Screens

↓

Features

↓

Product

---

### Reason

Stable foundations reduce redesign and improve consistency.

---

### Consequence

Foundation documents must be completed before large-scale feature development.

---

# Decision-010

## MVP Before Platform

Status

Accepted

---

### Decision

Validate one decision workflow before expanding to additional scenarios.

---

### Reason

Focus increases learning speed and reduces delivery risk.

---

### Consequence

Housing decision is the only supported scenario in MVP.

Other domains remain future roadmap items.

---

# Architecture Change Policy

Architecture changes must not be made directly.

Every significant change should follow this workflow:

RFC (Request for Comments)

↓

Discussion

↓

Architecture Review

↓

Approval

↓

Architecture Decision Update

↓

Implementation

---

# Decision Status

Possible values:

Accepted

Proposed

Deprecated

Superseded

Rejected

---

# Principles

Architecture decisions should be:

Stable

Simple

Traceable

Explainable

Long-term

---

# End of Document