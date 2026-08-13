---
name: dsh-short-story-engine
description: 维护与使用短篇状态机（稿件解析、五道门禁、状态流转、发布稿导出）时加载。 / Load when maintaining or using the short-story state machine (manuscript parsing, five gates, state transitions, publish export).
---

# 短篇小说状态机

短篇状态机 v0.1 面向番茄短篇一次成型赛制：外部 Agent 负责生成，本机做确定性验收。稿件按 `# 标题 / ## 导语 / ## 第N节 [钩子:xxx]` 的 markdown 约定解析；五道门禁（字数、导语、钩子、AI 味、试读截停）全部通过才进入 FINAL；返修最多三轮，耗尽进入 QUARANTINE。

The v0.1 short-story state machine targets the Fanqie one-shot format: external agents generate, this machine accepts deterministically. Manuscripts parse from the `# title / ## lead-in / ## section N [hook:xxx]` markdown convention; all five gates (word count, lead-in, hook, AI flavor, preview cut) must pass to reach FINAL; at most three revision rounds before QUARANTINE.

## When to use / 何时使用

需要调整门禁规则、解析稿件格式、排查状态流转，或导出番茄发布稿时。

## Workflow / 工作流

1. 读 core/state_machine.py 的模块文档与 config/short_story_config.json 的参数说明。
2. 用 parse_manuscript() 解析稿件，跑 gate_word / gate_lead_in / gate_hook / gate_ai_flavor / gate_preview_cut 五道门禁。
3. 用 audit() 执行 GATE_AUDIT 主流程；export_publish() 导出发布稿。
4. 修改门禁后运行 CLI 用样例稿件回归。

## References / 参考

- 项目 README: 见仓库根目录
- 作者: h565656445 (GitHub)