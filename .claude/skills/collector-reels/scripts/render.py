#!/usr/bin/env python3
"""plan.json -> 9:16 릴스 mp4 (장면 컷 + 상단 제목 + 하단 자막 번인).

plan.json:
{
  "title": "40년 모은 시계, 전부 공개",        # 상단 고정 제목 (\\n 줄바꿈 가능)
  "output": "reel_01.mp4",
  "layout": "blur",                            # blur(원본 전체+흐린 배경) | crop(중앙 크롭)
  "clips": [
    {"source": "E2JfJBmGa7s", "start": 63.2, "end": 71.8,
     "subtitles": [{"start": 63.2, "end": 66.0, "text": "처음엔 그냥 하나였어요"}]}
  ]
}
subtitles 시간은 원본 기준(초). 생략하면 transcript.json에서 해당 구간을 자동 사용.
"""
import argparse, json, pathlib, subprocess, sys, tempfile, shutil
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import rights

W, H = 1080, 1920
FONTS = ["Pretendard", "Noto Sans CJK KR", "NanumSquare", "NanumGothic", "Apple SD Gothic Neo", "Malgun Gothic"]

def pick_font(pref):
    if pref: return pref
    try:
        have = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True).stdout
        for f in FONTS:
            if f in have: return f
    except FileNotFoundError:
        pass
    return "Malgun Gothic"

def ass_time(t):
    t = max(t, 0); cs = int(round(t * 100))
    return f"{cs//360000}:{cs//6000%60:02d}:{cs//100%60:02d}.{cs%100:02d}"

def esc(s): return s.replace("{", "(").replace("}", ")").replace("\n", "\\N")

def wrap(text, n=16):
    if "\n" in text or len(text) <= n: return text
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > n:
            lines.append(cur); cur = w
        else:
            cur = f"{cur} {w}".strip()
    lines.append(cur)
    return "\n".join(lines)

def build_ass(title, events, total, font, st):
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,{font},{st['title_size']},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,6,0,8,60,60,{st['title_y']},1
Style: Accent,{font},{st['title_size']},&H0000E1FF,&H0000E1FF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,6,0,8,60,60,{st['title_y']},1
Style: Sub,{font},{st['sub_size']},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,1,0,0,0,100,100,0,0,1,5,2,2,80,80,{st['sub_y']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    if title:
        # 제목: [강조]텍스트[/강조] 지원 -> 노란색
        t = esc(title).replace("[", "{\\c&H00E1FF&}").replace("]", "{\\c&HFFFFFF&}")
        lines.append(f"Dialogue: 1,{ass_time(0)},{ass_time(total)},Title,,0,0,0,,{{\\fad(300,0)}}{t}")
    for s, e, txt in events:
        lines.append(f"Dialogue: 0,{ass_time(s)},{ass_time(e)},Sub,,0,0,0,,{{\\fad(80,80)}}{esc(wrap(txt, st['wrap']))}")
    return head + "\n".join(lines) + "\n"

def vf_layout(layout):
    if layout == "crop":
        return f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps=30"
    return (f"split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
            f"boxblur=30:3,eq=brightness=-0.15[bg];[b]scale={W}:-2[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,fps=30")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--work", default="work")
    ap.add_argument("--out", default="out")
    ap.add_argument("--font")
    ap.add_argument("--preview", action="store_true",
                    help="권리 미확인이어도 '게시 불가' 워터마크 붙인 내부 검토/허락 요청용 시안 생성")
    a = ap.parse_args()
    plan = json.loads(pathlib.Path(a.plan).read_text(encoding="utf-8"))
    srcs = list(dict.fromkeys(c["source"] for c in plan["clips"]))
    bad = {k: v for k, v in rights.check(a.work, srcs).items() if v}
    if bad and not a.preview:
        msg = "\n".join(f"  {k}: " + "; ".join(v) for k, v in bad.items())
        sys.exit(f"⛔ 권리 확인 안 된 소스가 있어 렌더 중단 ({rights.path(a.work)}):\n{msg}\n"
                 "  → 허락 받은 뒤 rights.json 갱신, 또는 --preview 로 시안만 생성")
    preview = bool(bad) or a.preview
    reg = rights.load(a.work)
    credits = [reg[s]["credit"] for s in srcs if reg.get(s, {}).get("credit")]
    root, outd = pathlib.Path(a.work), pathlib.Path(a.out); outd.mkdir(parents=True, exist_ok=True)
    font = pick_font(a.font or plan.get("font"))
    st = {"title_size": 78, "title_y": 230, "sub_size": 64, "sub_y": 380, "wrap": 16, **plan.get("style", {})}
    tmp = pathlib.Path(tempfile.mkdtemp())
    parts, events, offset = [], [], 0.0
    for i, c in enumerate(plan["clips"]):
        src = root / c["source"] / "source.mp4"
        s, e = float(c["start"]), float(c["end"]); dur = e - s
        part = tmp / f"p{i:02d}.mp4"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{s}", "-t", f"{dur}",
                        "-i", str(src), "-filter_complex", vf_layout(c.get("layout", plan.get("layout", "blur"))),
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "160k", str(part)], check=True)
        subs = c.get("subtitles")
        if subs is None:
            tj = root / c["source"] / "transcript.json"
            subs = [x for x in json.loads(tj.read_text())] if tj.exists() else []
            subs = [x for x in subs if x["end"] > s and x["start"] < e]
        for x in subs:
            ss, ee = max(x["start"], s) - s + offset, min(x["end"], e) - s + offset
            if ee > ss: events.append((ss, ee, x["text"]))
        parts.append(part); offset += dur
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    ass = tmp / "subs.ass"
    ass.write_text(build_ass(plan.get("title", ""), events, offset, font, st), encoding="utf-8")
    out = outd / plan.get("output", "reel.mp4")
    vf = f"ass={ass}"
    if preview:
        out = out.with_name(out.stem + "_PREVIEW" + out.suffix)
        wm = tmp / "wm.ass"
        wm.write_text(build_ass("", [(0, offset, "PREVIEW · 게시 불가")], offset, font,
                                {**st, "sub_size": 90, "sub_y": 900}).replace("&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000", "&H60FFFFFF,&H60FFFFFF,&H600000FF,&H96000000"),
                      encoding="utf-8")
        vf += f",ass={wm}"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-vf", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)], check=True)
    shutil.copy(ass, out.with_suffix(".ass"))
    cap = plan.get("caption", "")
    for c in credits:
        if c not in cap: cap = (cap + "\n\n" + c).strip()
    if cap:
        out.with_suffix(".txt").write_text(cap, encoding="utf-8")
    shutil.rmtree(tmp)
    print(f"[ok] {out}  ({offset:.1f}s, font={font}{', PREVIEW - 게시 불가' if preview else ''})")

if __name__ == "__main__":
    main()
