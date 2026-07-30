# LiveOS Sprint Definition of Done v1.0

---

## 目的

Definition of Done（DoD）用于判断一个 Sprint 是否可以关闭（Freeze）。

LiveOS 当前处于 MVP 阶段。

Sprint 是否完成，以产品交付为核心，而不是以完整工程体系为核心。

---

# Sprint 完成条件

一个 Sprint 满足以下全部条件，即可进入 Freeze。

## 1. 功能完成（Required）

本 Sprint 所有需求已经完成。

包括：

- 页面
- 交互
- 数据绑定
- Runtime 映射

全部符合本 Sprint Specification。

---

## 2. Architecture Review 通过（Required）

确认：

- 不违反 Product Boundary
- 不违反 Runtime Boundary
- 没有引入新的产品职责
- 没有扩大 Sprint Scope

Review 无 Blocker。

---

## 3. Build 通过（Required）

至少完成：

- TypeScript Check
- ESLint
- Production Build

全部通过。

---

## 4. Git 状态正常（Required）

要求：

```
git status
```

工作区干净。

无未提交修改。

---

## 5. Product Review 完成（Required）

产品体验符合预期。

允许存在：

- UI 微调
- 文案优化
- 小范围样式调整

这些进入下一 Sprint。

---

## 6. Sprint Freeze（Required）

Architecture 与 Product 均确认：

```
Sprint XX Freeze
```

进入下一 Sprint。

---

# 不阻塞 Sprint 的事项

以下事项不会阻止 Sprint 关闭：

- 自动化测试未完善
- CI 未建设
- E2E 未建设
- Storybook 未建设
- Test Coverage 不高
- Code Coverage 未统计
- 工程基础设施仍在建设

这些属于长期工程能力。

不属于 MVP Sprint Closing 条件。

---

# 阻塞 Sprint 的事项

以下问题必须修复：

- 页面无法访问
- Build 失败
- Runtime Mapping 错误
- Product Boundary 错误
- 数据展示错误
- 功能未完成
- 严重交互 Bug
- 导致下一 Sprint 无法继续的问题

---

# Sprint 状态

每个 Sprint 只有四种状态：

Planning

↓

Building

↓

Review

↓

Freeze

Freeze 后：

不再继续修改当前 Sprint。

新的修改进入下一 Sprint。

---

# Codex 判断标准

以后 Codex 判断 Sprint 是否完成时，应按照本 Definition of Done。

不要因为以下原因拒绝关闭 Sprint：

- 自动化测试未完成
- 工程体系未完善
- CI 未搭建

除非这些问题已经直接阻塞当前 Sprint 的产品交付。

---

# MVP 原则

LiveOS 当前阶段：

Product First

Architecture Second

Engineering Third

工程质量必须保证。

但工程体系建设不得阻塞产品能力迭代。

---

Version

LiveOS Sprint Definition of Done v1.0

Status

Frozen