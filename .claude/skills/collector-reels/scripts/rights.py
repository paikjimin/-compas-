#!/usr/bin/env python3
"""출처 대장(reels/rights.json) + 리스크 경고. 렌더를 막지 않고 경고만 한다.

  python rights.py init  --work reels/work      # 소스별 출처 항목 자동 생성
  python rights.py check --work reels/work [plan.json]   # 소스/릴스 리스크 경고 출력

항목: title, channel, url, youtube_license, basis(unlicensed|cc-by|permission|own),
      credit(캡션 자동 삽입 문구), notes
"""
import argparse, json, pathlib

# Content ID / Rights Manager 를 적극 운영하는 방송사·대형 채널 키워드
HIGH_RISK = ["KBS", "MBC", "SBS", "JTBC", "tvN", "TV CHOSUN", "TV조선", "채널A", "MBN", "EBS", "YTN", "연합뉴스",
             "CJ ENM", "Mnet", "디글", "Dingo", "딩고", "스브스", "엠뚜루마뚜루", "Netflix", "BBC", "CNN", "Discovery",
             "National Geographic", "Vice", "Bloomberg", "Insider"]

def path(work): return pathlib.Path(work).parent / "rights.json"

def load(work):
    p = path(work)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

def info(work, vid):
    f = pathlib.Path(work) / vid / "source.info.json"
    return json.loads(f.read_text()) if f.exists() else {}

def ensure(work, ids):
    reg, changed = load(work), False
    for i in ids:
        if i in reg: continue
        j = info(work, i); lic = j.get("license") or ""
        ch = j.get("channel") or j.get("uploader") or ""
        reg[i] = {"title": j.get("title", ""), "channel": ch, "url": j.get("webpage_url", ""),
                  "youtube_license": lic, "basis": "cc-by" if "Creative Commons" in lic else "unlicensed",
                  "credit": f"영상 출처: 유튜브 '{ch}' {j.get('webpage_url','')}".strip(), "notes": ""}
        changed = True
    if changed: path(work).write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
    return reg

def source_risks(work, vid, e):
    r, j = [], info(work, vid)
    if e.get("basis") == "unlicensed":
        r.append(("⚠", "허락/CC 없음 — 출처 표기만으로는 면책 안 됨 (신고 시 삭제·계정 경고 가능)"))
    if not e.get("credit"):
        r.append(("⚠", "출처 문구 비어 있음"))
    blob = f"{e.get('channel','')} {j.get('uploader','')} {j.get('channel','')}".lower()
    hit = [k for k in HIGH_RISK if k.lower() in blob]
    if hit:
        r.append(("🔴", f"방송사/대형 채널({', '.join(hit)}) — 자동 저작권 탐지·신고 가능성 높음"))
    if j.get("track") or j.get("artist") or "Music" in (j.get("categories") or []):
        r.append(("🔴", "음악 콘텐츠/음원 정보 감지 — 음원은 별도 권리, 자동 탐지 매우 잘 됨"))
    return r

def plan_risks(work, plan):
    r, used = [], {}
    for c in plan["clips"]:
        used[c["source"]] = used.get(c["source"], 0) + float(c["end"]) - float(c["start"])
    for vid, sec in used.items():
        dur = info(work, vid).get("duration") or 0
        if sec > 30: r.append(("⚠", f"{vid}: 한 소스에서 {sec:.0f}초 사용 — 길수록 원본 대체로 판단될 위험↑"))
        if dur and sec / dur > 0.1: r.append(("⚠", f"{vid}: 원본의 {sec/dur:.0%} 사용"))
    if not plan.get("commentary"):
        r.append(("ℹ", "내 해설/평가 텍스트 없음 — 원본 발췌 위주면 '인용'으로 인정받기 어려움"))
    return r

def report(work, srcs, plan=None):
    reg = ensure(work, srcs)
    lines = []
    for s in srcs:
        for lv, m in source_risks(work, s, reg[s]): lines.append(f"{lv} {s}: {m}")
    if plan:
        lines += [f"{lv} {m}" for lv, m in plan_risks(work, plan)]
    return reg, lines

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["init", "check"])
    ap.add_argument("plan", nargs="?")
    ap.add_argument("--work", default="reels/work")
    a = ap.parse_args()
    root = pathlib.Path(a.work)
    plan = json.loads(pathlib.Path(a.plan).read_text(encoding="utf-8")) if a.plan else None
    srcs = list(dict.fromkeys(c["source"] for c in plan["clips"])) if plan else \
        sorted(p.name for p in root.iterdir() if (p / "source.mp4").exists())
    _, lines = report(a.work, srcs, plan)
    print(f"[출처 대장] {path(a.work)}")
    print("\n".join(lines) or "✅ 경고 없음")

if __name__ == "__main__":
    main()
