# -*- coding: utf-8 -*-
"""短篇状态机 v0.1 —— 网络小说短篇一次成型赛制。

主态: INIT -> OUTLINE -> RETRIEVAL -> DRAFT -> GATE_AUDIT -> (REVISE<=3) -> PREVIEW_CUT -> FINAL
异常态: QUARANTINE(门禁不过且返修耗尽) / HALT(结构非法)

与长篇 novel_engine 的关系：复用其哲学（确定性门禁、fail-closed、钩子纪律），
但产物单位是"单篇"而非"章"，生成由外部 Agent 完成，本机只做确定性验收与状态流转。

稿件格式约定（markdown）：
    # 标题
    ## 导语
    ...导语正文...
    ## 第1节 [钩子:悬念]
    ...
    ## 第8节 [闭环]
    ...
"""
import json
import re
import sys
import io
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "short_story_config.json"
RUN_STATE_PATH = ROOT / "run_state.json"

MAIN_STATES = ["INIT", "OUTLINE", "RETRIEVAL", "DRAFT", "GATE_AUDIT", "REVISE", "PREVIEW_CUT", "FINAL"]
EXCEPTION_STATES = ["QUARANTINE", "HALT"]

SECTION_RE = re.compile(r"^##\s*第(\d+)节\s*(?:\[(?:钩子:)?([^\]]+)\])?\s*$")
LEAD_RE = re.compile(r"^##\s*导语\s*$")


def load_config():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _count_cn(text):
    """字数口径：去空白后字符数（与网络小说平台后台口径接近）。"""
    return len(re.sub(r"\s", "", text))


def parse_manuscript(md_text):
    """解析稿件为 {title, lead_in, sections:[{idx, hook, text}]}，结构非法返回 None。"""
    lines = md_text.splitlines()
    title, lead_in, sections = None, [], []
    cur = None  # "lead" | dict
    for ln in lines:
        if ln.startswith("# ") and title is None:
            title = ln[2:].strip()
            continue
        if LEAD_RE.match(ln):
            cur = "lead"
            continue
        m = SECTION_RE.match(ln)
        if m:
            cur = {"idx": int(m.group(1)), "hook": (m.group(2) or "").strip(), "text": []}
            sections.append(cur)
            continue
        if cur == "lead":
            lead_in.append(ln)
        elif isinstance(cur, dict):
            cur["text"].append(ln)
    if title is None or not sections:
        return None
    for s in sections:
        s["text"] = "\n".join(s["text"]).strip()
        s["chars"] = _count_cn(s["text"])
    return {"title": title, "lead_in": "\n".join(lead_in).strip(), "sections": sections}


# ---------------- 五道确定性门 ----------------

def gate_word(doc, cfg):
    g = cfg["word_gate"]
    total = sum(s["chars"] for s in doc["sections"])
    errs = []
    if not (g["story_min"] <= total <= g["story_max"]):
        errs.append(f"篇级字数{total}越界[{g['story_min']},{g['story_max']}]（超上限即被判中短篇档）")
    if len(doc["sections"]) < g["min_sections"]:
        errs.append(f"节数{len(doc['sections'])}<{g['min_sections']}")
    for s in doc["sections"]:
        if not (g["section_min"] <= s["chars"] <= g["section_max"]):
            errs.append(f"第{s['idx']}节字数{s['chars']}越界[{g['section_min']},{g['section_max']}]")
    return {"gate": "word_gate", "pass": not errs, "total_chars": total, "errors": errs}


def gate_lead_in(doc, cfg):
    g = cfg["lead_in_gate"]
    n = _count_cn(doc["lead_in"])
    errs = []
    if g["required"] and n == 0:
        errs.append("缺失导语（网络小说短篇必需）")
    elif not (g["min_chars"] <= n <= g["max_chars"]):
        errs.append(f"导语字数{n}越界[{g['min_chars']},{g['max_chars']}]")
    return {"gate": "lead_in_gate", "pass": not errs, "chars": n, "errors": errs}


def gate_hook(doc, cfg):
    """钩子从头到尾：开篇窗口内见冲突信号；每节末带白名单钩子；相邻不重复；末节闭环禁钩。"""
    g = cfg["hook_gate"]
    errs = []
    secs = doc["sections"]
    head = secs[0]["text"][: g["opening_hook_window_chars"]]
    if not any(sig in head for sig in g["opening_conflict_signals"]):
        errs.append(f"开篇前{g['opening_hook_window_chars']}字未见冲突信号{g['opening_conflict_signals'][:4]}...")
    prev_hook = None
    for s in secs[:-1]:
        if not s["hook"]:
            errs.append(f"第{s['idx']}节未标注节末钩子")
        elif s["hook"] not in g["taxonomy"]:
            errs.append(f"第{s['idx']}节钩子[{s['hook']}]不在白名单{g['taxonomy']}")
        elif g["rule_no_adjacent_repeat"] and s["hook"] == prev_hook:
            errs.append(f"第{s['idx']}节钩子[{s['hook']}]与上节重复")
        prev_hook = s["hook"]
    last = secs[-1]
    if last["hook"] != g["final_section_marker"]:
        errs.append(f"末节标记[{last['hook']}]应为[{g['final_section_marker']}]（短篇末节必须闭环不留钩）")
    return {"gate": "hook_gate", "pass": not errs, "errors": errs}


def gate_ai_flavor(doc, cfg):
    g = cfg["ai_flavor_gate"]
    full = doc["lead_in"] + "".join(s["text"] for s in doc["sections"])
    total = _count_cn(full)
    hits = [(w, full.count(w)) for w in g["blacklist"] if w in full]
    n_hits = sum(c for _, c in hits)
    density = n_hits * 1000.0 / max(total, 1)
    errs = []
    if density > g["max_hits_per_thousand"]:
        errs.append(f"AI味密度{density:.2f}/千字 > {g['max_hits_per_thousand']}，命中：{dict(hits)}")
    # 零容忍字符：破折号/方头括号等，命中一次即不过
    forb = [(w, full.count(w)) for w in g.get("forbidden_chars", []) if w in full]
    if forb:
        errs.append(f"零容忍字符命中：{dict(forb)}")
    return {"gate": "ai_flavor_gate", "pass": not errs, "hits": dict(hits),
            "forbidden_hits": dict(forb),
            "density_per_k": round(density, 3), "errors": errs}


def gate_preview_cut(doc, cfg):
    """试读截停：在窗口内的节边界上，选钩子属于高潮悬置类的最强点。"""
    g = cfg["preview_cut"]
    secs = doc["sections"]
    total = sum(s["chars"] for s in secs)
    lo, hi = g["window"]
    candidates, cum = [], 0
    for s in secs[:-1]:  # 末节闭环，永不作为截停点
        cum += s["chars"]
        ratio = cum / total
        if lo <= ratio <= hi and s["hook"] in g["allowed_cut_hooks"]:
            candidates.append({"cut_after_section": s["idx"], "ratio": round(ratio, 3), "hook": s["hook"]})
    if not candidates:
        return {"gate": "preview_cut", "pass": False, "candidates": [],
                "errors": [f"窗口{g['window']}内无高潮悬置类钩子节边界，需调整钩子排布或节切分"]}
    best = min(candidates, key=lambda c: abs(c["ratio"] - g["target_ratio"]))
    return {"gate": "preview_cut", "pass": True, "chosen": best, "candidates": candidates, "errors": []}


ALL_GATES = [gate_word, gate_lead_in, gate_hook, gate_ai_flavor]


# ---------------- 状态流转 ----------------

def load_run_state():
    if RUN_STATE_PATH.exists():
        return json.loads(RUN_STATE_PATH.read_text(encoding="utf-8"))
    return {"state": "INIT", "revise_rounds": 0, "history": []}


def save_run_state(st):
    RUN_STATE_PATH.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def transition(st, new_state, note=""):
    if new_state not in MAIN_STATES + EXCEPTION_STATES:
        raise ValueError(f"非法状态 {new_state}")
    st["history"].append({"from": st["state"], "to": new_state, "note": note})
    st["state"] = new_state
    return st


def audit(manuscript_path):
    """GATE_AUDIT 主流程：跑四门 + 试读截停，输出裁决。"""
    cfg = load_config()
    md = Path(manuscript_path).read_text(encoding="utf-8")
    doc = parse_manuscript(md)
    st = load_run_state()
    if doc is None:
        transition(st, "HALT", "稿件结构非法：缺标题或节标记")
        save_run_state(st)
        return {"verdict": "HALT", "reason": "稿件结构非法"}

    results = [g(doc, cfg) for g in ALL_GATES]
    preview = gate_preview_cut(doc, cfg)
    results.append(preview)
    failed = [r for r in results if not r["pass"]]

    if not failed:
        transition(st, "PREVIEW_CUT", f"四门全过，试读截停=第{preview['chosen']['cut_after_section']}节末 ({preview['chosen']['ratio']:.0%})")
        transition(st, "FINAL", "终锁")
        verdict = "PASS"
    else:
        st["revise_rounds"] += 1
        if st["revise_rounds"] > cfg["revision_max_rounds"]:
            transition(st, "QUARANTINE", f"返修{cfg['revision_max_rounds']}轮耗尽")
            verdict = "QUARANTINE"
        else:
            transition(st, "REVISE", f"第{st['revise_rounds']}轮返修：{sum(len(r['errors']) for r in failed)}项")
            verdict = "REVISE"
    save_run_state(st)
    return {"verdict": verdict, "state": st["state"], "revise_rounds": st["revise_rounds"],
            "gates": results, "title": doc["title"]}


def export_publish(manuscript_path, out_path=None):
    """导出发布稿：网络小说平台整篇一次发布，每节开头插纯数字章节标识（1/2/3，平台据此分章）；
    导语单独一块贴导语框。"第N节[钩子]"标记仅为引擎内部工作格式，不进发布稿。"""
    cfg = load_config()
    md = Path(manuscript_path).read_text(encoding="utf-8")
    doc = parse_manuscript(md)
    if doc is None:
        raise SystemExit("稿件结构非法，无法导出")
    preview = gate_preview_cut(doc, cfg)
    cut_tip = ""
    if preview["pass"]:
        c = preview["chosen"]
        cut_tip = f"试读卡点参考（如后台可设）：第{c['cut_after_section']}章末，累计 {c['ratio']:.0%} 处"
    body = "\n\n".join(f"{i}\n\n{s['text'].strip()}" for i, s in enumerate(doc["sections"], 1))
    out = Path(out_path) if out_path else Path(manuscript_path).with_name(
        Path(manuscript_path).stem + ".发布稿.txt")
    parts = [
        doc["title"],
        "",
        "==== 导语（贴导语框）====",
        doc["lead_in"].strip(),
        "",
        "==== 正文（整篇一次发布，纯数字分章）====",
        body,
    ]
    if cut_tip:
        parts += ["", "==== 备注（不进后台）====", cut_tip]
    out.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return {"out": str(out), "body_chars": _count_cn(body), "lead_chars": _count_cn(doc["lead_in"])}


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    if len(sys.argv) < 2:
        print("用法: python state_machine.py <manuscript.md> [--publish [out.txt]]")
        sys.exit(1)
    if "--publish" in sys.argv:
        args = [a for a in sys.argv[1:] if a != "--publish"]
        info = export_publish(args[0], args[1] if len(args) > 1 else None)
        print(json.dumps(info, ensure_ascii=False, indent=2))
        sys.exit(0)
    report = audit(sys.argv[1])
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(0 if report["verdict"] == "PASS" else 2)
