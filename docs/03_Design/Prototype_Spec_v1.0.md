# LiveOS Prototype Specification v1.0

**Project:** LiveOS

**Document Type:** Prototype Specification

**Version:** 1.0

**Status:** Active

**Related Documents**

- LiveOS_PRD_v3.0_Final
- LiveOS_Project_Context_v1.0
- LiveOS_Design_Context_v1.0

---

# 1. Prototype Goal

Validate the complete MVP user journey.

The prototype should demonstrate:

- AI Conversation
- User Understanding
- Living Profile
- Property Analysis
- AI Decision
- Memory

Prototype focuses on experience validation instead of backend implementation.

---

# 2. Design Objectives

The prototype should answer three questions:

1. Can users naturally communicate with AI?
2. Can AI build trust through reasoning?
3. Can users complete one housing decision?

---

# 3. Prototype Scope

Desktop Web

Responsive support

Minimum Width

1440px

Future

Tablet

Mobile

---

# 4. Navigation Structure

```

AI Entry

↓

Conversation

↓

Living Profile

↓

Workspace

↓

Comparison

↓

Decision

↓

Memory

```

Navigation is task-driven instead of menu-driven.

---

# 5. Screen List

| ID | Screen | Status |
|----|--------|--------|
| S01 | AI Entry | MVP |
| S02 | Conversation | MVP |
| S03 | Living Profile | MVP |
| S04 | Property Workspace | MVP |
| S05 | Property Detail | MVP |
| S06 | Property Comparison | MVP |
| S07 | AI Decision | MVP |
| S08 | Memory | MVP |

---

# 6. Screen Specification

---

## S01 AI Entry

Purpose

Create the first AI connection.

Components

- AI Orb
- Welcome Message
- Prompt Suggestions
- Input Box

User Action

Type a natural language request.

AI Action

Start conversation.

Next

Conversation

---

## S02 Conversation

Purpose

Understand user requirements.

Components

- Chat Bubble
- Streaming Response
- Suggested Questions
- Progress Indicator

AI Responsibilities

Ask questions.

Summarize understanding.

Extract preferences.

Output

Living Profile Draft.

---

## S03 Living Profile

Purpose

Visualize AI understanding.

Components

- Preference Card
- Lifestyle Card
- Commute Card
- Budget Card
- Editable Tags

User

Confirm

Edit

Delete

AI

Updates profile dynamically.

---

## S04 Property Workspace

Purpose

Manage candidate properties.

Components

- Property Card
- Upload Area
- Workspace Panel
- AI Summary

User

Add

Remove

Select

AI

Extracts structured information.

---

## S05 Property Detail

Purpose

Display detailed property analysis.

Sections

Overview

Pros

Cons

Commute

Budget Fit

Neighborhood

Lifestyle Match

AI Summary

---

## S06 Property Comparison

Purpose

Compare multiple candidates.

Layout

Comparison Table

Evaluation Matrix

Trade-off Summary

AI Recommendation

Comparison Dimensions

Budget

Commute

Space

Transportation

Lifestyle

Future Growth

Safety

Overall Fit

---

## S07 AI Decision

Purpose

Recommend the best option.

Output

Recommendation

Reasons

Trade-offs

Potential Risks

Confidence

Alternative Choice

Next Action

Users can:

Accept

Continue Comparing

Modify Preferences

---

## S08 Memory

Purpose

Store decision history.

Display

Past Decisions

Preference Evolution

Memory Timeline

Users may:

Review

Edit

Delete

---

# 7. Global Layout

Top Bar

Logo

Workspace

Profile

Settings

Main Area

AI Conversation

Content Panel

Right Panel

Context

Profile

Memory

---

# 8. AI States

Idle

Listening

Thinking

Understanding

Analyzing

Comparing

Generating

Completed

Error

Every state should have corresponding animation.

---

# 9. User States

First Visit

Returning User

Decision In Progress

Decision Completed

No Properties

Network Error

---

# 10. Component Library

Core Components

AI Orb

Prompt Input

Chat Bubble

Property Card

Decision Card

Profile Card

Memory Card

Comparison Table

Confidence Badge

Progress Step

Timeline

Modal

Toast

Loading

Empty State

---

# 11. Interaction Rules

One primary action per screen.

Progressive disclosure.

Avoid modal overload.

Keep interaction conversational.

Every AI recommendation must be explainable.

---

# 12. Prototype Data

Prototype uses mock data.

No real backend required.

Mock Objects

User

Living Profile

Property

Decision

Memory

Conversation

---

# 13. Prototype Success Criteria

Users can:

Complete one housing decision.

Understand AI reasoning.

Trust recommendations.

Navigate naturally.

Finish within 10 minutes.

---

# 14. Handoff Requirements

Prototype must support:

Figma

↓

Frontend Development

↓

Next.js

↓

React

↓

Tailwind CSS

Every screen should include:

Layout

Components

Interaction

State

Data Mapping

---

# 15. Future Extensions

Future prototype may include:

City Selection

Job Decision

School Selection

Life Planning

Financial Planning

Travel Decision

Health Decision

Prototype architecture should support future expansion without redesign.

---

# End of Document