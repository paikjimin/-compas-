#!/usr/bin/env python3
"""권리 확인 대장(reels/rights.json) 관리 + 검증.

  python rights.py init  --work reels/work           # 소스별 항목 생성(pending), CC BY는 자동 표시
  python rights.py check --work reels/work [ids...]  # 상태 출력, 미승인 있으면 exit 1

항목 예:
"E2JfJBmGa7s": {
  "title": "...", "channel": "...", "url": "...", "youtube_license": "Creative Commons Attribution license (reuse allowed)",
  "basis": "permission",            # permission(허락) | cc-by | own(직접 촬영/본인 채널) | pending
  "evidence": "2026-11-20 채널 메일 회신, drive/허락메일.pdf",   # 허락 근거(필수)
  "scope": "인스타 릴스 3편, 편집 허용", "expires": "2027-12-31",  # 선택
  "credit": "영상 출처: 유튜브 @채널명",                       # 캡션에 자동 삽입(필수)
  "portrait_ok": true,              # 출연자 초상 사용 동의(허락 범위에 포함 확인)
  "music_ok": true                  # 영상 속 배경음악 문제 없음(제거했거나 권리 확인)
}
"""
import argparse, datetime, json, pathlib, sys

VALID = {"permission", "cc-by", "own"}

def path(work): return pathlib.Path(work).parent / "rights.json"

def load(work):
    p = path(work)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

def problems(e):
    if not e: return ["권리 대장에 항목 없음 (rights.py init 실행)"]
    p = []
    b = e.get("basis", "pending")
    if b not in VALID: p.append(f"basis='{b}' — 허락/CC BY/직접촬영 확인 전")
    if b in ("permission", "cc-by") and not e.get("evidence"): p.append("evidence(허락 근거) 비어 있음")
    if b == "cc-by" and "Creative Commons" not in (e.get("youtube_license") or ""):
        p.append("유튜브 라이선스가 CC BY로 표시되지 않음")
    if b != "own" and not e.get("credit"): p.append("credit(출처 표기) 비어 있음")
    if e.get("expires") and e["expires"] < datetime.date.today().isoformat(): p.append(f"허락 기간 만료({e['expires']})")
    if e.get("portrait_ok") is not True: p.append("portrait_ok(출연자 초상 동의) 미확인")
    if e.get("music_ok") is not True: p.append("music_ok(배경음악 권리) 미확인")
    return p

def check(work, ids):
    reg = load(work)
    return {i: problems(reg.get(i)) for i in ids}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["init", "check"])
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--work", default="reels/work")
    a = ap.parse_args()
    root = pathlib.Path(a.work)
    ids = a.ids or sorted(p.name for p in root.iterdir() if (p / "source.mp4").exists())
    if a.cmd == "init":
        reg = load(a.work)
        for i in ids:
            if i in reg: continue
            info = root / i / "source.info.json"
            j = json.loads(info.read_text()) if info.exists() else {}
            lic = j.get("license") or ""
            reg[i] = {"title": j.get("title", ""), "channel": j.get("channel", ""), "url": j.get("webpage_url", ""),
                      "youtube_license": lic, "basis": "pending", "evidence": "", "scope": "", "expires": "",
                      "credit": f"영상 출처: 유튜브 {j.get('channel','')} ({j.get('webpage_url','')})",
                      "portrait_ok": None, "music_ok": None}
            if "Creative Commons" in lic:
                reg[i]["basis"] = "cc-by"; reg[i]["evidence"] = f"YouTube 라이선스 표시: {lic}"
        path(a.work).write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[ok] {path(a.work)}")
    res = check(a.work, ids)
    for i, p in res.items():
        print(f"{'✅' if not p else '⛔'} {i}" + ("" if not p else "\n   - " + "\n   - ".join(p)))
    sys.exit(1 if any(res.values()) else 0)

if __name__ == "__main__":
    main()
