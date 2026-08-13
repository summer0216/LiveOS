# LiveOS Development Workflow v2.0

## Purpose

规范 LiveOS 的产品、架构、工程协作流程，明确 Human 与 Codex 的职责边界。

------------------------------------------------------------------------

# Team Roles

## Product Owner（Human）

### Responsibilities

-   Product Decision
-   Priority Management
-   Final Acceptance
-   Git Management
-   Production Release

### Deliverables

-   Product Decision
-   Release Decision

------------------------------------------------------------------------

## Architecture Owner（ChatGPT）

### Responsibilities

-   Specification
-   Architecture
-   Scope Control
-   Build Document
-   Code Review
-   Architecture Review
-   Product Review

### Deliverables

-   Specification
-   Build
-   Review Report

------------------------------------------------------------------------

## Engineering Owner（Codex）

### Responsibilities

-   Coding
-   Validation
-   Build Report

### Deliverables

-   Git Diff
-   Validation Result
-   Build Report

------------------------------------------------------------------------

# Workflow

``` text
Product Decision
        │
        ▼
Specification
        │
        ▼
Build
        │
        ▼
Codex Implementation
        │
        ▼
Validation
        │
        ▼
Build Report + Git Diff
        │
        ▼
Code Review
        │
        ▼
Architecture Review
        │
        ▼
Product Review
        │
        ▼
Final Acceptance
        │
        ▼
Freeze
        │
        ▼
Git
        │
        ▼
Production
```

------------------------------------------------------------------------

# Handoff Rules

## ChatGPT → Codex

仅交付 Build。

不交付：

-   Product Discussion
-   PRD
-   Roadmap
-   Architecture Discussion

## Codex → ChatGPT

必须提供：

-   Git Diff（必需）
-   Validation（必需）
-   Build Report（辅助）

## ChatGPT → Product Owner

输出：

-   Code Review
-   Architecture Review
-   Product Review
-   Review Conclusion

------------------------------------------------------------------------

# Review Principles

Review 的对象永远是代码，而不是文字总结。

Review 输入：

1.  Git Diff
2.  Validation
3.  Build Report（辅助）

------------------------------------------------------------------------

# Engineering Principles

## One Task, One Build

一个 Build 一次完成：

-   Coding
-   Validation
-   Build Report

避免重复实施。

## Frozen First

Frozen Specification 完成后，不重新讨论产品设计。

## Scope Control

只实现当前 Task，禁止扩大 Scope。

## Minimal Change

优先最小修改，避免无关重构。

------------------------------------------------------------------------

# Review Result

Review 结束后统一输出：

``` text
Code Review
PASS / FAIL

Architecture Review
PASS / FAIL

Product Review
PASS / FAIL

Recommendation

Freeze
或
Return to Codex
```
