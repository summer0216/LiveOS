# LiveOS Decision Loop v1.0

**Status:** Frozen Product Model v1.0  
**Scope:** LiveOS MVP  
**Purpose:** 将 LiveOS 从「AI 对话辅助」进一步收敛为真正的 AI Decision System，并作为后续 Runtime、Decision、Action、Memory 与 Main Experience 设计和开发的产品基准。

---

## 1. Product Definition

LiveOS 的核心循环不是：

```text
User Message
    ↓
AI Response
    ↓
User Message
    ↓
AI Response
```

而是：

```text
Situation
    ↓
Current Judgment
    ↓
Decision Gap
    ↓
Primary NEXT
    ↓
Reality Action
    ↓
Evidence
    ↓
Updated Judgment
    ↓
Next Decision Gap
    ↓
...
```

> **LiveOS 是一个持续形成判断、识别关键未知、推动现实验证，并根据现实结果更新判断的 AI Decision System。**

Conversation 是交互方式。Decision Loop 才是产品主体。

---

## 2. Decision Loop

```text
USER GOAL
   ↓
CURRENT JUDGMENT
   ↓
DECISION GAP
   ↓
PRIMARY NEXT
   ↓
REALITY ACTION
   ↓
EVIDENCE
   ↓
UPDATED JUDGMENT
   ↓
NEXT DECISION GAP
   ↓
...
```

Decision Loop 可以运行多轮，直到关键不确定性降低到足以支持行动：

```text
Decision Gap sufficiently reduced
                ↓
          READY DECISION
```

LiveOS 追求的不是信息完整，而是 **Decision Sufficiency（决策充分性）**。

---

## 3. Four First-Class Decision States

MVP 将以下四个状态提升为用户真正应该感知的一级产品状态：

1. **Current Judgment** — 当前判断
2. **Decision Gap** — 最关键的未知
3. **Primary NEXT** — 下一步最值得做的事
4. **Latest Reality** — 最近现实 / 最新证据

Candidate、Profile、Conversation、Memory 等对象继续存在，但主要作为这些 Decision State 的上下文和支撑。

---

## 4. Current Judgment

> 基于当前已知信息，LiveOS 对当前问题最合理的判断。

Current Judgment 不是最终答案，也不是不可改变的推荐。它允许随着证据变化：形成 → 增强 → 削弱 → 反转 → 替换。

有效的 Current Judgment 应尽可能表达：

```text
方向 + 当前确定程度 + 保留条件
```

例如：

> 目前更倾向龙华这套，但还不建议定下来。价格和居住条件符合，但平台显示的 28 分钟通勤尚未验证。

---

## 5. Decision Gap

Decision Gap 是 Decision Loop v1.0 的核心概念。

> **当前阻止 LiveOS 做出更可靠判断的、最值得优先消除的不确定性。**

Decision Gap 不是所有缺失信息，而是最可能改变当前判断、因此最值得优先解决的那个未知。

例如用户已经提供龙华候选房 ¥5200、平台通勤 28 分钟、喜欢房子但没有实际走过路线。虽然还缺楼层、朝向、物业费等信息，当前真正重要的 Decision Gap 是：

> 工作日真实门到门通勤是否真的接近 28 分钟？

核心原则：

```text
Missing Data ≠ Decision Gap
```

只有可能改变判断的信息，才值得成为当前 Decision Gap。

---

## 6. Decision Gap Types

### 6.1 Fact Gap

事实未知，例如实际通勤多久、晚上噪音是否严重、实际采光怎么样。

```text
Fact Gap
   ↓
Reality Action
   ↓
Evidence
   ↓
Gap Reduced
```

### 6.2 Preference Gap

用户自身的权衡偏好尚未形成，例如：

> 我不知道应该更看重通勤还是居住空间。

此时真正的不确定性不是缺一个数字，而是用户尚不知道自己如何权衡两个价值。Preference Gap 不能简单通过继续追问事实解决。

LiveOS 应帮助用户形成或验证偏好，并通过真实体验逐渐形成 Preference Evidence 与 Learned Preference。

---

## 7. Primary NEXT

> **为了降低当前 Decision Gap，现在最值得用户做的一件事。**

Primary NEXT 不是 AI 接下来想问什么，也不是普通建议列表。

```text
Decision Gap
      ↓
Primary NEXT
```

弱 NEXT：

> 你能告诉我 B 的通勤时间吗？

强 NEXT：

> 选一个正常工作日早高峰，从小区门口到公司门口完整走一次，记录门到门时间、换乘等待和出站步行时间。

好的 Primary NEXT 应尽可能具备：明确对象、明确行动、明确观察内容、明确目的。

---

## 8. Reality Action

当用户接受 Primary NEXT：

```text
Primary NEXT
      ↓
ActionRecord
      ↓
WAITING_FOR_REALITY
```

LiveOS 不需要继续制造大量对话，而应该等待现实世界产生新的信息。

这意味着 LiveOS 可以跨越现实行动继续一个 Decision。

---

## 9. Evidence / Latest Reality

例如用户回来报告：

> 昨天下班实际走了一次，37 分钟，出地铁还要走 10 分钟，感觉有点累。

这里同时可能存在：

- **Fact Evidence:** 实际门到门 37 分钟。
- **Experience Evidence:** 用户感觉明显疲劳。

Reality Evidence 应优先于平台描述、预估数据和 AI 假设。

---

## 10. Updated Judgment

Reality Evidence 进入后，LiveOS 必须重新评估当前判断。

```text
Previous Judgment
      ↓
Reality Evidence
      ↓
Updated Judgment
      ↓
READY ?
  ├─ YES → Ready Decision
  └─ NO  → New Decision Gap → New Primary NEXT
```

Judgment 必须能够被现实证据增强、削弱或推翻。

---

## 11. Decision Sufficiency

LiveOS 不追求“所有信息完整”，而追求：

> **信息是否已经足够支持当前行动或选择。**

即使仍不知道物业公司、楼龄、停车位等信息，只要这些未知当前不足以改变判断，LiveOS 就可以进入 `READY`。

---

## 12. Ready Decision

Decision Loop 的阶段性终点是 `READY DECISION`。

一个 Ready Decision 应至少能够表达：

- Recommendation / 当前建议
- Why / 主要依据
- Trade-off / 主要取舍
- Reality / 已验证现实
- 当前证据是否足以支持行动

READY 不意味着 Decision Loop 永久结束。现实发生变化后，Decision 可以重新进入 Reevaluation。

---

## 13. Conversation Role

Conversation 重新定义为：

> **Decision Loop 的自然语言 I/O Layer。**

```text
Conversation
      ↓
AI Runtime
      ↓
Decision State
```

而不是：

```text
Conversation = Product
```

Conversation 服务 Decision Loop，而不是 Decision Loop 服务 Conversation。

---

## 14. Candidate Role

Candidate 是 **Decision Subject / Option**，支撑 Judgment，但不驱动产品本身。

```text
NO CANDIDATE ≠ NO DECISION
```

没有结构化 Candidate 时，LiveOS 仍然可以理解问题、形成初步 Judgment、识别 Decision Gap、生成 Primary NEXT。

---

## 15. Profile Role

Profile 的职责是 **Decision Context**。

```text
Candidate
    +
Profile
    +
Evidence
    +
Memory
    ↓
Judgment
```

Profile 不应成为用户旅程本身。

---

## 16. Memory Role

Memory 不只是记住用户说过什么，更重要的是：

> **记住过去 Decision Loop 形成的 Decision Learning。**

例如：

```text
Stated Preference
        ↓
Reality Evidence
        ↓
Learned Preference
```

这类 Memory 才是 LiveOS 的长期价值之一。

---

## 17. AI Runtime Responsibilities

LiveOS 继续采用：

> **Single Runtime, Multiple Logical Agents.**

现有 Logical Agents 围绕 Decision Loop 服务：

- Conversation Agent → 理解 Situation
- Profile Agent → 维护 Decision Context
- Property Agent → 理解 Candidate
- Decision Agent → Current Judgment / Decision Gap / Primary NEXT
- Memory Agent → 消费 Reality / Decision Learning

每轮 Runtime 不应只判断“我要怎么回复用户？”，还应该判断：

1. 当前 Judgment 是否变化？
2. 当前最重要的 Decision Gap 是什么？
3. 是否已经拥有足够信息？
4. 如果不足，什么 Reality Action 最能降低这个 Gap？
5. 用户这条消息是否提供了 Evidence？
6. Evidence 是否足以改变 Judgment？
7. 是否形成了值得进入 Memory 的 Learning？

---

## 18. Existing Architecture Mapping

Decision Loop v1.0 不推倒现有架构。

| Decision Loop | Existing LiveOS |
|---|---|
| User Goal | Conversation / Profile |
| Current Judgment | DecisionRecord |
| Decision Gap | **需要 Audit 确认承载方式** |
| Primary NEXT | ActionRecord |
| Reality Action | ActionRecord / WAITING |
| Evidence / Latest Reality | VerificationEvidence |
| Updated Judgment | DecisionRecord |
| Decision Learning | Learning / Memory |
| Resume | Resume Projection |

当前最明显的结构缺口是：

> **Decision Gap 是否已经被 Runtime 结构化表达。**

这需要 Architecture Audit，而不是立即数据库重构。

---

## 19. Main Experience Information Architecture

Main Experience 推荐顺序：

```text
当前问题 / User Goal
        ↓
当前判断 / Current Judgment
        ↓
最关键的未知 / Decision Gap
        ↓
下一步 / Primary NEXT
        ↓
最近现实 / Latest Reality
        ↓
候选方案 / Candidate
        ↓
最近对话 / Conversation
```

右侧 `Live Context` 继续作为 Decision Context 存在。

视觉主线必须是：

```text
Judgment
   ↓
Gap
   ↓
NEXT
   ↓
Reality
```

---

## 20. Main Experience State Machine

```text
FORMING
   ↓
GAP_IDENTIFIED
   ↓
ACTION_READY
   ↓
WAITING_FOR_REALITY
   ↓
EVIDENCE_RECEIVED
   ↓
REEVALUATING
   ├────────→ GAP_IDENTIFIED
   └────────→ READY
```

现实变化后：

```text
READY
  ↓
REALITY_CHANGED
  ↓
REEVALUATING
```

---

## 21. Product Invariants

### D1 — Decision is Primary
LiveOS 的主要产品状态是 Decision，不是 Conversation。

### D2 — Judgment is Provisional
Judgment 可以随着现实证据持续变化。

### D3 — One Primary Gap
每个阶段最多突出一个最重要的 Decision Gap。

### D4 — NEXT Resolves Gap
Primary NEXT 必须明确服务于当前 Decision Gap。

### D5 — Reality Beats Assumption
实际 Evidence 的优先级高于平台描述和 AI 假设。

### D6 — Missing Data ≠ Decision Gap
缺少信息不代表必须收集；只有可能改变判断的信息才值得成为 Gap。

### D7 — Preference is Evidence
用户真实体验和逐渐形成的偏好也是 Decision Evidence。

### D8 — Conversation is Secondary
Conversation 服务于 Decision Loop，而不是反过来。

---

## 22. MVP Boundary

Decision Loop v1.0 暂时不做：

- 多 Decision Gap 排序系统
- 复杂置信度模型
- 自动信息增益计算
- Decision Graph
- 多层 Goal Tree
- 自动 Agent Planning
- Preference Vector
- 强化学习
- 新独立 Agent
- 新独立 Runtime
- 大规模数据库重构

MVP 只要求：

> **任何时刻尽可能找到一个最重要的 Decision Gap，并产生一个最值得执行的 Primary NEXT。**

---

## 23. Case Validation

Decision Loop v1.0 来源于 Main Experience 重构后的实际运行验证，而不是单纯从抽象 PRD 推导。

| Case | 核心问题 | 结果 |
|---|---|---|
| 1 | 平台通勤时间未经验证 | 完整出现 Judgment → Fact Gap → Reality Action |
| 2 | 预算 vs 居住质量 | Trade-off 正确，Primary NEXT 仍需加强 |
| 3 | 双人通勤冲突 | 能识别不平衡，但 Action 仍偏信息追问 |
| 4 | 用户自身偏好不明确 | 暴露 Preference Gap 能力缺口 |
| 5 | 新 Reality Evidence 改变判断 | 完整出现 Reality → Updated Judgment → New Gap → New NEXT |

测试表明：

> LiveOS 的 Decision Intelligence 已经部分存在于 Runtime 推理中，但尚未完整成为结构化、持续可见的产品状态。

---

## 24. Reference Decision Loop Example

### Situation
龙华之前感觉不错。

### Previous Judgment
龙华值得继续考虑。

### Reality
实测 37 分钟，出站还走 10 分钟，而且觉得累。

### Updated Judgment
龙华的真实通勤体验明显弱于原预期。

### New Candidate
宝安 ¥6500，比预算高 ¥500，平台通勤 25 分钟。

### Decision Gap
宝安真实通勤是否能明显改善龙华已经暴露出的通勤疲劳问题？

### Primary NEXT
在相近工作日下班时间实际走一次宝安 → 公司路线。

### Future Evidence
实际 27 分钟，步行 4 分钟，明显轻松。

### Updated Judgment
宝安虽然每月多 ¥500，但真实通勤改善明显，当前更值得选择。

### READY

```text
Recommendation: 宝安
Trade-off:
+ ¥500 / month
- ~20 min round-trip commute
+ significantly better subjective experience
```

---

## 25. Product Formula

LiveOS MVP 可以进一步收敛为：

> **LiveOS = Judgment + Gap + Action + Reality + Learning**

展开：

```text
Understand
   ↓
Judge
   ↓
Find what matters most
   ↓
Act
   ↓
Observe reality
   ↓
Learn
   ↓
Judge again
```

`Conversation + Profile + Property + Decision + Memory` 仍然可以作为系统能力与模块模型；`Judgment + Gap + Action + Reality + Learning` 则是更接近用户实际体验的产品模型。

---

## 26. Freeze Boundary

**LiveOS Decision Loop v1.0 在此冻结为 Product Model v1.0。**

冻结内容：

- Decision Loop 核心模型
- 四个 First-Class Decision State
- Decision Gap 概念
- Fact Gap / Preference Gap 基础分类
- Primary NEXT 与 Gap 的因果关系
- Reality → Updated Judgment 闭环
- Product Invariants
- MVP Boundary

冻结不代表底层实现已经确定。以下内容仍需通过现有代码和架构 Audit 确认：

- Decision Gap 当前是否已经存在于 Runtime 输出中
- Decision Gap 是否需要新增持久化字段
- Primary NEXT 是否已被结构化生成
- Main Experience 是否能直接从现有 Record 投影四个一级状态
- Resume 如何恢复完整 Decision Loop State

---

## 27. Next Step — Decision Loop Architecture Audit

下一步不是立即 Build，也不是继续视觉重构。

Audit 现有：

```text
DecisionRecord
ActionRecord
VerificationEvidence
Learning
Resume
AI Runtime
Frontend Projection
```

只回答三个核心问题：

1. **Decision Gap 现在实际上存在于哪里？**
2. **Primary NEXT 是否已经由 Runtime 结构化产生，还是主要藏在 AI 文本里？**
3. **能否不改 Backend Schema，就先把 Judgment → Gap → NEXT → Reality 稳定投影出来？**

原则：

> **先 Audit，后 Build。**

如果现有架构已经能够承载 Decision Loop，应优先采用最小增量实现，而不是再次进行大规模重构。

---

**End of LiveOS Decision Loop v1.0**
