# LiveOS Development Workflow v1.0

**Status:** Frozen  
**Project:** LiveOS MVP  
**Last Updated:** 2026-07-30

---

# Purpose

本文档定义 LiveOS MVP 阶段的标准开发流程。

目标：

- 保持开发节奏稳定
- 保持 Product、Architecture、Engineering 职责清晰
- 避免需求不断变化
- 避免过度设计
- 快速完成 MVP

本 Workflow 为团队开发规范。

除非进行版本升级，否则不随 Sprint 临时修改。

---

# Team Roles

## Product Owner

负责：

- 产品方向
- 功能优先级
- 产品体验
- Sprint 验收
- Freeze 决策

不负责：

- 代码实现
- Runtime 设计
- 工程实现细节

---

## AI Architect（ChatGPT）

负责：

- Product Architecture
- Runtime Boundary
- Sprint Planning
- Task Specification
- Architecture Review
- Product Review
- Sprint Freeze

不负责：

- 实际代码实现
- 擅自扩大 Sprint Scope
- 修改已经 Freeze 的产品设计

---

## AI Engineer（Codex）

负责：

- 根据 Specification 实现代码
- Bug 修复
- Build
- Type Check
- ESLint
- 提交 Implementation Report

不负责：

- 修改产品设计
- 修改 Runtime
- 擅自增加功能
- 擅自重构架构
- 擅自扩大任务范围

---

# Development Principle

LiveOS 当前阶段：

**MVP First**

所有开发遵循：

> 最小修改（Minimal Change）
>
> 最小实现（Minimal Implementation）
>
> 最大可运行（Maximum Working Product）

不要为了未来增加抽象。

不要为了未来增加层级。

不要为了未来增加复杂架构。

---

# Sprint Workflow

每个 Sprint 固定四个阶段。

```

Planning

↓

Architecture

↓

Build

↓

Review

↓

Freeze

```

不得跳过 Review。

Freeze 后结束当前 Sprint。

---

# Stage 1 — Planning

负责人：

Product + AI Architect

目标：

确定：

- Sprint Theme
- 唯一目标
- Scope
- Out of Scope

输出：

```

Sprint Plan

```

Planning 不进入 Codex。

---

# Stage 2 — Architecture

负责人：

AI Architect

目标：

明确：

- Purpose
- Responsibilities
- Boundary
- Runtime Mapping

Architecture 只讨论职责。

不讨论实现。

输出：

```

Architecture Review

```

Architecture 不进入 Codex。

---

# Stage 3 — Build

负责人：

AI Architect → Codex

AI Architect 输出：

```

SprintXX_Build.md

```

统一格式：

- 背景
- 唯一目标
- 修改范围
- 页面结构
- 实现规则
- 禁止修改
- 验证场景
- 代码质量
- 验证命令
- 最终输出格式

Codex 根据 Specification 实现。

不得自行增加需求。

不得修改产品设计。

---

# Stage 4 — Review

负责人：

AI Architect

Review 内容：

- 是否符合 Product
- 是否符合 Runtime
- 是否符合 Specification
- 是否存在 Blocker

如果存在问题：

输出：

```

SprintXX_Review.md

```

Review 只描述：

- 问题
- 修改要求
- 验证要求

不要重新描述整个需求。

---

# Stage 5 — Freeze

负责人：

Product + AI Architect

确认：

- Build 完成
- Review 完成
- Product 验收完成

宣布：

```

Sprint XX Freeze

```

之后：

当前 Sprint 不再新增需求。

所有新增需求进入下一 Sprint。

---

# Codex Document Standard

所有交付给 Codex 的任务必须为完整 Markdown 文档。

统一命名：

```

SprintXX_Build.md

SprintXX_Review.md

```

禁止聊天式任务描述。

禁止多轮补充需求。

一次 Specification 应完整表达任务。

---

# Scope Control

每个 Sprint：

只有一个主题。

例如：

- Living Profile
- Property Workspace
- AI Decision

禁止：

一个 Sprint 同时完成多个核心能力。

---

# Change Control

已经 Freeze 的内容：

不得因为想到更好的方案而修改。

允许修改的情况只有：

## 1.

产品方向发生变化。

例如：

MVP

↓

Beta

↓

V1

---

## 2.

开发验证当前规范存在明显问题。

例如：

- Codex 连续理解错误
- Specification 存在缺陷
- Workflow 阻碍开发效率

此时：

升级 Workflow 版本。

例如：

```

Workflow v1.1

```

不得直接修改 v1.0。

---

# MVP Principle

当前阶段：

重点不是：

- 最完美架构
- 最完整工程体系

重点是：

持续完成产品能力。

所有讨论必须回答：

> 当前 Sprint 唯一目标是什么？

以及：

> 当前代码最小需要修改什么？

如果不能回答：

停止设计。

---

# Versioning

Workflow 使用版本管理。

例如：

```

Workflow v1.0

Workflow v1.1

Workflow v2.0

```

旧版本保持冻结。

升级必须明确记录原因。

---

# Current Version

**Workflow:** v1.0

**Status:** Frozen