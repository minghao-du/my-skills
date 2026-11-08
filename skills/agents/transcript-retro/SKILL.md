---
name: transcript-retro
description: 对智能体对话转录日志（含所有 Subagent 子代理记录）进行客观、循证的复盘审计，提取技能演进、规范优化、工具固化与上下文治理建议。
disable-model-invocation: true
---

# 对话转录复盘（Transcript Retro）

对智能体对话转录记录进行客观、证据驱动的会话后复盘。**默认自动递归发现并读取所有子代理（Subagent）的完整对话转录**，全景追踪控制面（父智能体调度）与数据面（子代理实际执行、工具调用、环境试错）的真实执行因果链路，系统化提取现有技能改进、工作区规范（`AGENTS.md`）、新技能孵化、确定性脚本固化、上下文卫生治理与用户提示词优化建议。

---

## 执行拓扑（零上下文污染）

在已有冗长且充满噪声的对话中直接进行复盘会消耗大量上下文 Token 并引入后验偏差。为保持纯净、零污染并节省 Token：

- **主推模式（子代理派发 / Subagent Delegation）**：
  在活动会话中被调用时，当前会话仅作为轻量调度器（Dispatcher）。定位目标会话转录路径后，派发一个全新、独立的子代理（`Role: Transcript Auditor`）。子代理在完全干净的独立上下文窗口中执行复盘提取、深度因果审计并生成 Markdown 报告，完成后向调度器汇报结果。
- **直接模式（Direct Mode）**：
  在全新的空会话中执行，或在不支持子代理调用的宿主环境中，智能体直接在当前会话运行提取脚本并完成审计。

---

## 输入参数

- **转录路径**（可选）：目标 `transcript.jsonl` 文件或会话目录路径。若省略，定位脚本将自动探测最新或最相关的会话。
- **`--offset N`**（可选）：分析前第 N 个历史会话（如 `--offset 1` 为倒数第二个会话）。
- **输出路径**（可选）：复盘报告 `.md` 目标文件路径（默认为 `./reports/retro-<session_id>.md`）。
- **`--no-subagents`**（可选）：禁用子代理自动递归发现，仅审计当前会话单层记录。
- **`--friction-only`**（可选）：聚焦审查发生工具报错、重试试错、上下文膨胀或用户纠偏的关键摩擦步骤。
- **`--full`**（可选）：展开全部子代理的逐步完整流水（默认采用“分层聚合”策略防上下文膨胀）。
- **`--max-depth N`**（可选）：子代理递归最大深度（默认值为 2）。

---

## 标准工作流

### 1. 定位目标转录文件（Resolve Target Transcript）

运行定位器以自动寻找目标会话的转录路径：

```bash
python3 <skill-dir>/scripts/find_transcript.py [optional-path] [--offset N]
```

完成标准：在磁盘上确认有效的转录文件绝对路径。若存在多个候选或路径存疑，可使用 `--list` 参数查看最近的候选会话。

---

### 2. 确定派发路径（Determine Dispatch Path）

- **若宿主环境支持 `invoke_subagent`（推荐主推路径）**：
  派发独立的审计子代理在干净窗口中执行审计。**切勿在当前父会话中直接倾倒或读取转录大文件**。
  
  调用 `invoke_subagent` 参数如下：
  - **TypeName**: `"self"`（或 `"research"`）
  - **Role**: `"Transcript Auditor"`
  - **Prompt**:
    ```text
    你是一名客观、独立的第三方对话转录审计员（Transcript Auditor）。请对以下会话转录进行端到端复盘分析：
    <resolved-transcript-path>

    执行说明：
    1. 提取结构化数据：
       运行命令：python3 <skill-dir>/scripts/extract_retro_context.py "<resolved-transcript-path>"
       （注意：该脚本已默认启用多智能体递归发现，会自动提取所有子代理的对话、指标矩阵与摩擦热点）
    2. 多智能体因果链路审计（Multi-Agent Hierarchy Audit）：
       - 父智能体控制面：调度契约是否清晰？任务拆解与参数传递是否存在歧义或遗漏？
       - 子智能体执行面：子代理内部的工具调用摩擦、环境报错、重复试错和算力资源调度是否存在瓶颈？
       - 跨代理协作断层：问题根因是父智能体引导不当，还是子智能体技能缺失或未按规约执行？
    3. 深入 6 大核心复盘维度：
       - 1. 现有技能审查（提前结束 premature completion、发散 sprawl、规则沉积 sediment、完成标准模糊）
       - 2. AGENTS.md 与工作区规范（添加明确的正面约束，避免重复踩坑）
       - 3. 新技能孵化（识别具备清晰前置动词、检查标准的重复多步操作）
       - 4. 确定性脚本与工具固化（将脆弱的临时 bash/python 逻辑沉淀为 scripts/ 确定性脚本）
       - 5. 上下文卫生治理（检查 >10KB 大文件倾倒、缺乏渐进式披露、未过滤日志）
       - 6. 用户提示词与交互人体工学（用户意图歧义点、智能体错失确认暂停点）
    4. 撰写结构化复盘报告至：<output-path>（默认路径：./reports/retro-<session_id>.md）
    5. 返回执行摘要、多智能体度量概览、前 3 项最高优先级改进行动项（Action Items）及本地文件链接。
    ```
  完成标准：子代理完成审计，向主调度器回复报告路径与高优先级建议。直接跳至 [步骤 5](#5-交付复盘成果摘要)。

- **若直接执行（不支持子代理或已在新会话中）**：
  在本地顺序执行步骤 3 与步骤 4。

---

### 3. 提取执行流水与多智能体摩擦（Direct Mode）

运行确定性提取脚本，在零上下文污染的前提下获取紧凑的多智能体度量与摩擦热点：

```bash
python3 <skill-dir>/scripts/extract_retro_context.py <resolved-transcript-path> [--friction-only]
```

完成标准：加载多智能体层级度量矩阵（Agent 拓扑、步数、工具调用、时长）、子代理摩擦热点（`TOOL_ERROR`、`CONTEXT_BLOAT`、`USER_STEERING` 等事件），控制在紧凑上下文阈值内。

---

### 4. 围绕 6 维度展开深度审计并编写报告（Direct Mode）

结合多智能体因果链路与提取出的事实数据，对会话进行逐项核查。每项结论必须标注具体的 `[Step N]` 或 `[Agent: Role / Step N]` 证据：

1. **现有技能审查（Existing Skills Audit）**：
   - 调用的技能是否存在**提前结束**（未完成真正验收即退出）、**发散游离**（偏离主线执行多余操作）或**规则沉积**（过时规则造成干扰）？
   - 技能交付物与完成判定标准是否具备确定性、二元可校验？
2. **工作区规约与 AGENTS.md（AGENTS.md & Workspace Rules）**：
   - 智能体是否在环境命令、工作区目录规范、数据分层、测试预算上反复摸索或违背规则？
   - 应当向 `AGENTS.md` 写入什么具体、正向的行为约束？
3. **新技能孵化机遇（New Skills Induction）**：
   - 智能体是否手工执行了高频、多步骤且容易出错的流程？
   - 该流程是否具备明确的触发动词、输入参数和可量化验收边界？
4. **确定性脚本与工具固化（Deterministic Tooling & Scripts Extraction）**：
   - 智能体是否在多次交互中即兴拼接复杂的 shell/python 单行命令？
   - 是否应将其固化为 `scripts/` 下带参数校验与错误处理的确定性脚本？
5. **上下文卫生与渐进式披露（Context Hygiene & Progressive Disclosure）**：
   - 是否有步骤直接向上下文 dump 了 >10KB 的全量日志或源码文件？
   - 是否应采用子集过滤、统计脚本或按需阅读实现渐进式披露？
6. **用户提示与交互人体工学（User Prompt Ergonomics & Clarification）**：
   - 用户初始 Prompt 是否存在语义二义性或需求超载？
   - 智能体在面对关键分支路线时是否主动发起了结构化澄清询问（如 `ask_question`）？

按照 [复盘报告模板](#复盘报告模板) 撰写报告至 `./reports/retro-<session_id>.md`。

完成标准：报告文件写入磁盘且非空（`test -s <output-path>`），并包含具体的代码/配置/Diff 改进提议。

---

### 5. 交付复盘成果摘要（Deliver Executive Summary）

在聊天对话中向用户交付清晰、精简的总结：
- **核心度量指标**：会话 ID、总耗时、总步数、子代理数量及工具调用分布。
- **多智能体全景**：展示各 Agent（控制面 vs 数据面）的职责、步数与摩擦占比。
- **Top 3 杠杆改行动项**：列出最关键的 3 项改进，明确指出需要修改或新增的文件。
- **报告链接**：提供可点击的本地绝对路径链接（`file:///...`）。

---

## 复盘报告模板

统一采用以下格式输出至 `./reports/retro-<session_id>.md`：

```markdown
# 智能体对话复盘审计报告：`<session_id>`

- **转录文件**: `<transcript_path>`
- **执行宿主**: `<antigravity | claude-code | cline>`
- **总步数**: `<total_steps>` | **工具调用**: `<total_tool_calls>` | **执行耗时**: `<duration>`
- **子代理数**: `<subagents_count>`（主控制面: 1 | 子执行面: `<N>`）

---

## 执行摘要（Executive Summary）
<用 2-3 句话总结本次会话的核心意图、最终交付结果、以及在控制面与子代理执行面中观察到的主要摩擦点>

---

## 多智能体全景度量（Multi-Agent Metrics Landscape）

| 智能体 (Agent) | 职责角色 (Role) | 步数 (Steps) | 工具调用 (Tools) | 报错 (Errors) | 摩擦点 (Frictions) | 耗时 (Duration) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Root Session | Orchestrator / Dispatcher | ... | ... | ... | ... | ... |
| Subagent-1 | Planning Specialist | ... | ... | ... | ... | ... |
| Subagent-2 | Implementation Specialist | ... | ... | ... | ... | ... |
| ... | ... | ... | ... | ... | ... | ... |

---

## 摩擦热点分析（Friction Hotspots）

| 发生节点 (Agent / Step) | 摩擦类型 (Type) | 现象与表现 (What Happened) | 根本原因剖析 (Root Cause) |
| :--- | :--- | :--- | :--- |
| `[Subagent: Implementation / Step 24]` | Tool Error | 运行脚本报错缺少依赖或语法错误 | 脚本未做前置防御检查 |
| `[Root / Step 5]` | Context Bloat | 巨型日志 dump (58KB) | 缺少分页或过滤直接查看全文 |

---

## 6 维度改进建议（Actionable Recommendations）

### 1. 现有技能审查（Existing Skills）
- **目标技能**: `<skill-name>`（或 "无"）
- **现存问题**: <提前结束 / 发散游离 / 规则沉积 / 标准模糊>
- **建议修改**:
  ```diff
  ...
  ```

### 2. AGENTS.md 与工作区规约（AGENTS.md & Workspace Conventions）
- **观察到的踩坑现象**: <智能体在何处反复尝试或偏离项目既定规范>
- **建议新增的正面约束**:
  > [!TIP]
  > <明确、具有可操作性的正面规则语句，可直接追加到 AGENTS.md>

### 3. 新技能孵化机会（New Skills Induction）
- **提议技能名称**: `<skill-name>`
- **触发场景与条件**: <何时调用>
- **核心执行流程**: <关键步骤提炼>

### 4. 确定性脚本与工具固化（Deterministic Tooling & Scripts）
- **候选逻辑**: <临时拼凑的 ad-hoc 命令或频繁重复的逻辑>
- **提议固化脚本**: `scripts/<script_name>.py`（附核心功能与接口定义）

### 5. 上下文卫生与渐进披露（Context Hygiene & Progressive Disclosure）
- **膨胀热点节点**: <包含过大 Payload 的步骤>
- **治理策略**: <增加截断过滤、使用统计摘要脚本或流式读取>

### 6. 用户提示与交互人体工学（User Prompt & Clarification Ergonomics）
- **交互瓶颈观察**: <提示词二义性或智能体未能在关键分叉点主动暂停澄清>
- **改进启发**: <更佳的提示词结构或智能体主动确认节点设计>

---

## 优先级行动清单（Prioritized Action Checklist）
- [ ] **P0**: <最高优先级修复，消除严重摩擦与环境阻碍>
- [ ] **P1**: <次高优先级改进，提升单次交互效率与质量>
- [ ] **P2**: <长期演进项，进一步完善技能生态与确定性工具>
```
