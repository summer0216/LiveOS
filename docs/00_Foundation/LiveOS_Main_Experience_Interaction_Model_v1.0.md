# LiveOS Main Experience Interaction Model v1.0

**Project:** LiveOS\
**Phase:** Beta-05 Product Upgrade\
**Type:** Product Interaction Architecture\
**Version:** v1.0\
**Status:** FROZEN

------------------------------------------------------------------------

## 1. Purpose

本模型定义 LiveOS 在完成 Beta-05 Grounded Decision Intelligence
之后的核心交互方式。

目标不是重新设计一套页面，而是回答：

> **LiveOS 作为 AI Native Decision
> Product，用户应该如何与它持续完成一个现实决策？**

本模型建立在已经冻结的产品决策之上：

``` text
Living Model ≠ Journey Step
Workspace ≠ Decision Prerequisite
Compare ≠ Fixed Step
Decision ≠ Step 7
```

以及新的 Information Architecture：

``` text
Decision Space
Candidates Space
Journey Space

+
Global Live Context
```

------------------------------------------------------------------------

## 2. Core Product Model

LiveOS 的主体验不是 Chat，也不是 Dashboard，更不是 Step-by-Step Software
Workflow。

正式定义为：

> **Living State + Conversation**

其中：

``` text
Living State = 当前问题已经推进到了什么状态
Conversation = 用户与 LiveOS 改变这个状态的自然语言通道
```

关系：

``` text
Reality
   ↓
Conversation
   ↓
AI Runtime
   ↓
Living State
   ↓
Next Action
   ↓
Reality
```

LiveOS 的核心产品对象不再是 Message，而是 **Decision State**。

------------------------------------------------------------------------

## 3. Main Experience Principle --- One Space, Evolving State

一个现实问题始终存在于同一个 Decision Space。

``` text
Decision Space

Understanding
      ↓
Direction
      ↓
Candidate
      ↓
Grounded Decision
      ↓
Action
```

这些是 State，不是 Page。用户始终感受到："我们还在解决同一个问题。"

------------------------------------------------------------------------

## 4. Main Experience Stable Anchors

### 4.1 Current Problem

始终回答：**我们现在正在解决什么？**

### 4.2 Living State

主界面的核心，回答：**事情现在发展到哪里？**

``` text
Understanding → Direction → Candidate → Decision → Action
```

### 4.3 Live Context

回答：**LiveOS 当前理解的用户与现实约束是什么？**

例如：

``` text
工作地点  成都高新区合作路89号
预算      ¥2200 / 月
居住方式  独居
通勤目标  ≤30分钟
```

用户可以查看、纠正、补充，但不需要管理 Profile。

------------------------------------------------------------------------

## 5. Conversation Role

Conversation 仍然是 LiveOS 最重要的 Interaction Channel，但 Conversation
不再等于产品本身。

它负责用户表达现实问题、提供新信息、纠正
LiveOS、提供现实反馈、改变优先级、Challenge
当前判断、要求进一步解释以及推进下一步。

``` text
Conversation = How the state changes
Living State = Where we are now
```

------------------------------------------------------------------------

## 6. Experience States

### S0 --- Intent

用户开始一个新的现实问题。重点是：

``` text
What are you trying to decide?
```

不首先展示 Profile、Workspace、Compare、Memory 或 Decision Status。

### S1 --- Understanding

LiveOS 已经识别问题及关键上下文。重点不是 Profile 完整度，而是 **LiveOS
已经理解了什么**。

### S2 --- Direction

信息还不足以形成具体 Decision，但已经足够形成方向。

体现 Beta-04 原则：

> Decision before Perfection\
> Progress before Completeness

### S3 --- Candidate

用户提供具体方案，Candidate 可以直接从 Conversation 产生，不要求先进入
Workspace。

### S4 --- Grounded Decision

当信息与 Evidence 足够，Living State 升级为 CURRENT DECISION，并回答：

-   What --- LiveOS 建议什么？
-   Why --- 为什么？
-   Evidence --- 现实依据是什么？
-   Trade-off --- 用户需要接受什么取舍？
-   Next Action --- 下一步应该做什么？

### S5 --- Action

Decision 不是结束，LiveOS 必须推动：

``` text
Decision → Action
```

------------------------------------------------------------------------

## 7. Working Candidate 与 Saved Candidate

**Working Candidate**：当前 Conversation / Decision
中正在分析的现实对象，可以临时存在。

**Saved Candidate**：已经判断值得持续考虑，并保存到 Candidates Space
的方案。

``` text
User mentions option
        ↓
Working Candidate
        ↓
AI evaluates
        ↓
Worth continuing?
     │        │
    NO       YES
     │        │
 结束分析   Save Candidate
              ↓
       Candidates Space
```

Candidate 可以先于 Workspace 存在。

------------------------------------------------------------------------

## 8. Decision Visual Priority

一旦 Decision 形成：

> **Decision State 的视觉优先级必须高于 Conversation History。**

Decision 不应该只是聊天流中的一条 Message Bubble，而必须表现为明确的
Product State。

------------------------------------------------------------------------

## 9. Evidence Presentation

Evidence 必须被用户感知，但不是一级产品模块。

原则：

> **Evidence 服务 Trust，不服务操作。**

不制造 Evidence Center、Evidence Management 或 Evidence Search UI。

------------------------------------------------------------------------

## 10. Trade-off Presentation

Trade-off 是 Decision Intelligence 的核心价值，不能藏在长篇 AI 文案里。

用户应该能够快速看见：

> **自己到底在交换什么。**

------------------------------------------------------------------------

## 11. Reality Loop

新的现实事实可以更新已有 Decision：

``` text
Existing Decision
       ↓
New Evidence
       ↓
Re-evaluate
       ↓
Updated Decision
```

Decision 不是一次性 AI Response，而是 **Living Decision State**。

Decision History 保存演进，Memory 从演进中学习。

------------------------------------------------------------------------

## 12. State Transitions

产品状态由信息变化驱动，而不是页面点击驱动。

``` text
New Information
      ↓
Runtime Evaluates
      ↓
State Transition
```

例如：

``` text
提供工作地点 → Context Updated
提供具体房源 → Candidate Appears
Evidence 足够 → Decision Appears
提供现实反馈 → Decision Updated
```

------------------------------------------------------------------------

## 13. State Is Non-linear

``` text
                 ┌────────────────┐
                 │                │
                 ▼                │
Intent → Understanding            │
             ↓                    │
         Direction                │
             ↓                    │
         Candidate ◄──────────────┤
             ↓                    │
      Grounded Decision           │
             ↓                    │
           Action                 │
             ↓                    │
           Reality ───────────────┘
```

LiveOS 必须支持：

> Understand → Decide → Act → Learn → Re-decide

------------------------------------------------------------------------

## 14. Recent Conversation

Decision Space 默认突出 **Recent Conversation**，只显示最近且与当前
Living State 最相关的交流。

完整 Conversation History 按需查看。

Returning User 应先看到 CURRENT DECISION，而不是昨天最后一句聊天。

------------------------------------------------------------------------

## 15. Structured Objects Emerge from Conversation

Conversation 可以自然产生：

``` text
Context
Candidate
Evidence
Trade-off
Decision
Action
```

但不形成 Message / Card 不断交错堆叠。所有结构化对象最终服务于 **Living
State**。

------------------------------------------------------------------------

## 16. Spatial Stability

正式原则：

> **Stable Space, Dynamic Intelligence**

即：

``` text
位置稳定
语义演进
内容更新
```

同一个 Living State 区域可以演进：

``` text
CURRENT UNDERSTANDING
        ↓
CURRENT DIRECTION
        ↓
CURRENT CANDIDATE
        ↓
CURRENT DECISION
```

避免自动跳页、大量弹窗、不断新增 Panel 或 AI 随意改变 Navigation。

------------------------------------------------------------------------

## 17. Main Experience Layout Model

``` text
┌─────────────────────────────────────────────────────────┐
│ LiveOS                  Candidates   Journey   + New    │
├─────────────────────────────────────────┬───────────────┤
│ CURRENT PROBLEM                         │ LIVE CONTEXT  │
│                                         │               │
│ ┌─────────────────────────────────────┐ │ 工作          │
│ │ LIVING STATE                        │ │ 预算          │
│ │                                     │ │ 居住方式      │
│ │ Understanding / Direction /         │ │ 通勤          │
│ │ Candidate / Decision / Action       │ │               │
│ └─────────────────────────────────────┘ │               │
│                                         │               │
│ Recent Conversation                     │               │
│                                         │               │
│ [继续告诉 LiveOS…]                      │               │
└─────────────────────────────────────────┴───────────────┘
```

这是 Interaction Model，不是最终视觉设计。

------------------------------------------------------------------------

## 18. Main Experience Product Language

新版 LiveOS 主体验由三个概念组成：

-   **Living State** --- 事情现在是什么状态？
-   **Conversation** --- 我们怎样改变它？
-   **Live Context** --- LiveOS 基于什么理解我？

辅助空间：

``` text
Candidates
Journey
```

------------------------------------------------------------------------

## 19. Human Control Boundary

LiveOS 负责：

``` text
理解
查证
分析
权衡
判断
建议
推进
```

用户负责：

``` text
确认
纠正
选择
行动
```

核心原则：

> **AI owns the process.\
> User owns the final choice.**

------------------------------------------------------------------------

## 20. Frozen Interaction Principles

### ME-01 --- One Space, Evolving State

一个现实问题在同一个 Decision Space 中持续演进。

### ME-02 --- Living State + Conversation

主体验采用 Living State + Conversation + Live Context，不采用纯 Chat
Timeline 或传统 Dashboard。

### ME-03 --- State Represents Now

Conversation 表达过程；Living State 表达当前状态。

### ME-04 --- Six Experience States

Intent / Understanding / Direction / Candidate / Grounded Decision /
Action 是 State，不是 Page。

### ME-05 --- Structured Objects Emerge Naturally

Context、Candidate、Evidence、Decision、Action 可以由 Conversation
自然产生，用户不需要进入对应功能创建。

### ME-06 --- Decision Has Visual Priority

Decision 一旦形成，其视觉优先级高于 Conversation History。

### ME-07 --- Decision Is Living

新的现实信息可以更新已有 Decision。

### ME-08 --- Information Drives State

状态变化来自 New Information → Runtime → Updated State，而不是 Next
Button → Next Page。

### ME-09 --- Stable Space, Dynamic Intelligence

AI 可以主动更新状态，但保持空间稳定。

### ME-10 --- Recent Conversation by Default

默认突出 Current State 与最近交流，完整 Conversation History 按需查看。

### ME-11 --- Evidence Serves Trust

Evidence 用于解释和增强 Decision Trust，不成为独立操作模块。

### ME-12 --- Decision Leads to Action

每个有意义的 Decision 都应该产生可执行 Next Action。

------------------------------------------------------------------------

## 21. Scope Boundary

Main Experience Interaction Model v1.0 不定义：

-   具体视觉风格
-   字体
-   Color
-   Card 样式
-   动画
-   最终 Navigation 名称
-   Route 结构
-   Component Architecture
-   API 修改
-   Runtime 修改
-   Data Schema 修改

这些属于下一阶段。

------------------------------------------------------------------------

## 22. Product Success Test

新版 Main Experience 是否成功，只需要问三个问题：

1.  用户打开 LiveOS 后，能不能立刻知道：**我现在正在解决什么？**
2.  用户能不能立刻知道：**事情现在推进到了哪里？**
3.  用户能不能立刻知道：**下一步该做什么？**

如果答案都是 Yes，Main Experience 成立。

如果用户仍然需要先想"我应该点击哪个功能？"，Interaction Model 失败。

------------------------------------------------------------------------

## 23. North Star

> **LiveOS 主体验是一个围绕现实问题持续演进的 Living Decision Space。**

用户提供现实。

LiveOS 持续：

``` text
Understand
   ↓
Ground
   ↓
Decide
   ↓
Act
   ↓
Learn
   ↓
Re-decide
```

用户不需要操作 AI 的内部能力，只需要继续面对自己的现实问题。

------------------------------------------------------------------------

## Freeze Record

**Version:** v1.0\
**Status:** FROZEN\
**Phase:** Beta-05 Product Upgrade

该文档自冻结起成为后续 Main Experience UI
Structure、Navigation、Decision Space、Candidates Space、Journey
Space、Live Context 以及相关 Build Specification 的交互基线。

后续实现不得在 Build 阶段自行改变本文冻结的核心 Interaction
Principles；如需改变，应重新进行产品决策并形成新的版本。
