# LiveOS 智能能力蓝图 v1.0

> 状态：Draft
>
> 阶段：Intelligence Era
>
> 更新时间：2026-08
>
> 负责人：Product / AI Runtime

---

# 一、文档定位

第一阶段，我们完成了 LiveOS AI Runtime 的基础建设。

包括：

- Conversation Runtime（持续对话）
- Living Profile（生活画像）
- Property Workspace（房源工作台）
- Decision Runtime（决策运行时）
- Decision History（决策历史）
- Decision Memory（决策记忆）
- AI Core Runtime（统一 AI Core）
- Experience System（统一体验系统）

至此，LiveOS 已经具备了完整的 AI Runtime。

从这一刻开始，我们进入第二阶段：

> **Intelligence Era（智能演进阶段）**

第二阶段不再关注：

> AI 能不能完成任务？

而是关注：

> AI 能不能持续成长。

因此，本文档定义 LiveOS 在第二阶段的智能能力演进方向，并作为后续所有 Sprint 的最高指导文档。

---

# 二、第二阶段愿景

LiveOS 不追求拥有最大的模型。

LiveOS 追求拥有最好的理解能力。

AI 的价值，不在于回答更多问题。

而在于：

- 更理解用户；
- 更会推理；
- 更会学习；
- 更能帮助用户做出长期决策。

每一次交互，都应该让 AI 比昨天更了解用户。

每一次决策，都应该让 AI 比昨天更聪明。

---

# 三、第一阶段回顾

第一阶段解决的是：

> **Build the Runtime**

我们完成了 AI Runtime 的基础能力。

包括：

✓ 持续对话

✓ 持续理解

✓ 持续画像

✓ 房源管理

✓ 决策生成

✓ 决策历史

✓ 长期记忆

✓ AI Core

✓ Runtime Experience

这些能力共同构成了 LiveOS 的运行框架。

但是：

这些能力更多解决的是：

> **AI 能不能工作。**

第二阶段要解决的是：

> **AI 能不能持续成长。**

---

# 四、智能能力架构

LiveOS Intelligence 由四项核心能力组成：

```text
                AI Runtime
                     │
     ┌───────────────┼───────────────┐
     │               │               │
 持续理解         智能推理        持续学习
     │               │               │
     └───────────────┼───────────────┘
                     │
                 长期规划
```

四项能力共同运行于同一个 AI Runtime。

整个系统始终坚持：

> **Single AI Runtime**

不存在多个独立 AI。

只有一个不断成长的 AI。

---

# 五、四大智能能力

## 5.1 持续理解（Understanding）

### 当前能力

目前 LiveOS 已能够：

- 提取用户信息；
- 更新 Living Profile；
- 建立基础画像；
- 保存历史信息。

### 下一阶段目标

建立真正的 Living Model（生活模型）。

AI 不再只是记录：

"用户说了什么。"

而是开始理解：

"用户为什么这样选择。"

例如：

工作地点：

↓

生活中心：

↓

通勤半径：

↓

生活方式：

↓

推荐居住区域。

最终形成持续演进的生活模型。

---

## 5.2 智能推理（Reasoning）

### 当前能力

目前 Decision Runtime 已能够：

生成推荐；

输出 Summary；

输出 Reasons；

输出 Trade-offs。

### 下一阶段目标

建立真正的 Decision Intelligence。

每一个 Recommendation 都必须能够解释：

为什么推荐？

为什么不是其它方案？

哪些因素影响了最终结果？

所有 Recommendation 都应建立在：

Evidence

↓

Reasoning

↓

Trade-offs

↓

Recommendation

↓

Confidence

之上。

真正做到：

**可解释的 AI 决策。**

---

## 5.3 持续学习（Learning）

### 当前能力

目前系统已经具备：

Decision Memory；

Memory Context；

Memory Prompt。

Memory 已进入 Runtime。

### 下一阶段目标

Memory 不再只是保存。

而是学习。

例如：

用户连续多次选择：

通勤优先。

AI 应主动提升：

通勤偏好。

用户长期保持：

预算稳定。

AI 应逐渐形成：

长期偏好。

Memory 将从：

Storage

演进为：

Learning。

---

## 5.4 长期规划（Planning）

这是第二阶段最终目标。

AI 不仅帮助用户完成今天的决策。

更帮助用户规划未来。

例如：

今天预算：

6000 元。

半年后：

预算提高。

AI 应提前规划：

是否换房？

什么时候换？

换到哪里？

Planning 关注的是：

长期生活决策。

而不是一次回答。

---

# 六、智能演进原则

未来所有 Sprint，都应遵循以下原则。

## 原则一

理解优先于回答。

不要追求回答更长。

而要追求理解更深。

---

## 原则二

证据优先于推荐。

所有 Recommendation 都必须建立在明确 Evidence 之上。

---

## 原则三

Memory 必须成长。

Memory 不应该成为数据库。

Memory 应成为 AI 的长期认知。

---

## 原则四

Planning 面向未来。

AI 不只是帮助今天。

更帮助未来。

---

## 原则五

每一次交互，都让 AI 更聪明。

任何一次 Conversation，

都不应该成为孤立事件。

所有 Interaction 都应该持续提升 AI Intelligence。

---

# 七、研发原则

第二阶段开始：

研发方式正式调整。

第一阶段：

以模块开发为中心。

Conversation

↓

Profile

↓

Workspace

↓

Decision

↓

Memory

第二阶段：

以智能能力开发为中心。

持续理解

↓

智能推理

↓

持续学习

↓

长期规划

以后所有 Sprint，

都围绕 Intelligence 展开。

而不是围绕页面展开。

---

# 八、Sprint 评估标准

从第二阶段开始。

Sprint 是否成功，

不再以：

新增多少功能。

作为标准。

而是回答四个问题：

AI 是否更理解用户？

AI 是否更会推理？

AI 是否更会学习？

AI 是否更能帮助用户做出决策？

如果答案是否定的，

则说明本次 Sprint 没有真正提升 LiveOS Intelligence。

---

# 九、最终目标

LiveOS 希望成长为：

一个能够持续理解用户、

持续学习用户、

持续推理问题、

持续帮助用户做出生活决策的 AI Runtime。

AI Runtime 始终保持一致。

真正不断成长的，

是其中的 Intelligence。

---

# 十、核心理念

第一阶段，我们构建 Runtime。

第二阶段，我们培养 Intelligence。

LiveOS 不只是一个 AI 产品。

它是一套能够持续成长的 AI Runtime。