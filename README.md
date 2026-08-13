# dsh-short-story-engine

<!-- DeepSeek Harness 衍生声明 -->
> **DeepSeek Harness 个人适配声明（Personal Adaptation Notice）**
>
> 本项目是 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) 的**个人适配产物（personal adaptation）**，**并非 DeepSeek Harness 官方文件（not an official DeepSeek Harness file）**，随附功能、使用说明与个人产物（bundled with features, documentation, and personal artifacts），可与 DeepSeek Harness 搭配使用，也可独立使用。
>
> This project is a **personal adaptation** for DeepSeek Harness, and is **NOT an official DeepSeek Harness file**, bundled with features, documentation, and personal artifacts. It can be used alongside DeepSeek Harness or standalone.

**作者 / Author**: [h565656445](https://github.com/h565656445)

**合作 / Collaboration**: 如有项目可以一起合作，欢迎联系。微信：`wohaishihenshuaide`。If you have projects, let's collaborate. WeChat: `wohaishihenshuaide`.

---

## 用途 / What this is for

短篇故事引擎：短篇状态机 core 与配置，INIT→OUTLINE→RETRIEVAL→DRAFT 的主态流转。

Short story engine: the short-form state machine core and config.

---
## Short Story Engine / 短篇小说状态机

短篇状态机 v0.1 —— 番茄短篇一次成型赛制。主态 `INIT → OUTLINE → RETRIEVAL → DRAFT → GATE_AUDIT → (REVISE ≤ 3) → PREVIEW_CUT → FINAL`；异常态 `QUARANTINE`（门禁不过且返修耗尽）与 `HALT`（结构非法）。生成由外部 Agent 完成，本机只做确定性门禁验收与状态流转。

Short-story state machine v0.1 for the Fanqie one-shot contest format. Main states: `INIT → OUTLINE → RETRIEVAL → DRAFT → GATE_AUDIT → (REVISE ≤ 3) → PREVIEW_CUT → FINAL`; exception states `QUARANTINE` (gates failed and revisions exhausted) and `HALT` (structurally invalid manuscript). Generation is delegated to an external agent; the machine only performs deterministic gate acceptance and state transitions.

## Features / 功能

- 五道确定性门禁：字数门、导语门、钩子门、AI 味检测、试读截停 / Five deterministic gates: word count, lead-in, hook discipline, AI-flavor detection, preview cut
- fail-closed 异常态：门禁不过且返修耗尽进入 QUARANTINE，结构非法进入 HALT / Fail-closed exception states
- 配置驱动：所有阈值、白名单与禁词集中在 config/short_story_config.json / Config-driven: thresholds, whitelists and banned words live in config/short_story_config.json
- 发布稿导出：--publish 生成整篇一次发布稿（纯数字分章，节标记不进发布稿）/ Publish export via --publish (single-shot submission; section markers stay internal)

## What's inside / 目录结构

```
core/state_machine.py          状态机、稿件解析、五道门禁、状态流转、发布稿导出（CLI 入口）
config/short_story_config.json 字数/导语/钩子/AI 味/试读截停参数与平台规则
```

## Quick start / 快速开始

```powershell
# 运行一次门禁审计（稿件须符合内部节标记格式：## 第N节 [钩子:xxx]）
python core/state_machine.py <manuscript.md>

# 导出发布稿（整篇一次发布，纯数字分章，导语单独贴导语框）
python core/state_machine.py <manuscript.md> --publish [out.txt]
```

## DeepSeek Harness 衍生 / DSH Derivative

本项目附带 DeepSeek Harness 衍生包，位于 `.dsh/` 目录：

- `preset.yml` — Agent 预设元数据
- `agent.cordis.yml` — Cordis 组装（基于 standard 预设，persona 已定制）
- `skills/dsh-short-story-engine/SKILL.md` — 项目专属技能（skill）

安装与接入方式见 [`.dsh/README.md`](.dsh/README.md)（双语）。

## License / 许可证

[MIT](LICENSE)