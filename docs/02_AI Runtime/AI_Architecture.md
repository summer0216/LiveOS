## 第一章：AI 的职责（最重要）

这一章其实只有一句话：

AI 不是聊天机器人。

AI 是：
```
用户

↓

Conversation

↓

理解用户

↓

更新 Living Profile

↓

分析房源

↓

比较房源

↓

给出决策

↓

形成长期 Memory
```

所以 AI 是：

LiveOS 的操作系统。

不是一个 Chat。

## 第二章：AI Runtime
整个 Runtime 其实非常简单。
```
User Message

↓

Context Builder

↓

Prompt Builder

↓

LLM

↓

Structured Output

↓

Decision

↓

Memory Update
```
六步。

结束。

## 第三章：Context Engine

我认为这是 LiveOS 最大的创新。

每次调用模型，

不是把聊天记录发过去。

而是：
```
Conversation

+

Living Profile

+

Property

+

Memory

+

Current Task
```
一起组成 Context。

所以以后 Prompt 永远不用写很长。

## 第四章：Decision Engine

AI 不负责回答。

AI 负责：
```
Recommendation

↓

Reasons

↓

Trade-off

↓

Confidence

↓

Next Action
```
这就是我们前面一直坚持的：Decision Card。

## 第五章：Memory Engine

Memory 也不要搞得很复杂。

MVP 只需要三层：
```
Conversation Memory

↓

Living Profile

↓

Decision History
```

以后再加：Semantic Memory。