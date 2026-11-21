#!/usr/bin/env python3
"""소스 분석: 전사(faster-whisper, 없으면 vtt) + 장면 전환 감지 + 키프레임 -> analysis.md"""
import argparse, json, pathlib, re, subprocess

def transcribe(src, model_size):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None
    m = WhisperModel(model_size, device="auto", compute_type="auto")
    segs, _ = m.transcribe(str(src), language="ko", vad_filter=True)
    return [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()} for s in segs]

def parse_vtt(d):
    vtts = sorted(d.glob("source*.vtt"))
    if not vtts:
        return []
    ts = lambda t: sum(float(x) * 60 ** i for i, x in enumerate(reversed(t.replace(",", ".").split(":"))))
    out, seen = [], set()
    for block in vtts[0].read_text(encoding="utf-8").split("\n\n"):
        m = re.search(r"([\d:.]+) --> ([\d:.]+)", block)
        if not m: continue
        lines = [re.sub(r"<[^>]+>", "", l).strip() for l in block.splitlines()[1:] if "-->" not in l]
        text = " ".join(l for l in lines if l)
        if text and text not in seen:
            seen.add(text)
            out.append({"start": round(ts(m[1]), 2), "end": round(ts(m[2]), 2), "text": text})
    return out

def scenes(src, thr):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(src), "-vf",
                        f"select='gt(scene,{thr})',showinfo", "-an", "-f", "null", "-"],
                       capture_output=True, text=True)
    return [round(float(x), 2) for x in re.findall(r"pts_time:([\d.]+)", r.stderr)]

def keyframes(src, d, every):
    kd = d / "frames"; kd.mkdir(exist_ok=True)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
                    "-vf", f"fps=1/{every},scale=480:-2", str(kd / "t%04d.jpg")], check=True)
    return sorted(kd.glob("t*.jpg"))

def fmt(t): return f"{int(t//60):02d}:{t%60:05.2f}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*", help="비우면 work/ 아래 전체")
    ap.add_argument("--work", default="work")
    ap.add_argument("--model", default="small")
    ap.add_argument("--scene", type=float, default=0.35)
    ap.add_argument("--frame-every", type=int, default=10)
    a = ap.parse_args()
    root = pathlib.Path(a.work)
    ids = a.ids or [p.name for p in root.iterdir() if (p / "source.mp4").exists()]
    for vid in ids:
        d = root / vid; src = d / "source.mp4"
        tr = d / "transcript.json"
        if tr.exists():
            segs = json.loads(tr.read_text())
        else:
            segs = transcribe(src, a.model) or parse_vtt(d)
            tr.write_text(json.dumps(segs, ensure_ascii=False, indent=1))
        sc = scenes(src, a.scene)
        (d / "scenes.json").write_text(json.dumps(sc))
        frames = keyframes(src, d, a.frame_every)
        meta = json.loads((d / "meta.json").read_text()) if (d / "meta.json").exists() else {}
        md = [f"# {vid} — {meta.get('title','')}", f"채널: {meta.get('channel','')}  길이: {meta.get('duration','')}s", "",
              f"## 장면 전환 ({len(sc)})", ", ".join(fmt(t) for t in sc) or "-", "",
              f"## 키프레임 (frames/tNNNN.jpg, {a.frame_every}초 간격: tNNNN = (NNNN-1)*{a.frame_every}s)", "",
              "## 전사"]
        md += [f"[{s['start']:.2f}-{s['end']:.2f}] {s['text']}" for s in segs]
        (d / "analysis.md").write_text("\n".join(md), encoding="utf-8")
        print(f"[ok] {vid}: {len(segs)} segs, {len(sc)} scenes, {len(frames)} frames -> {d/'analysis.md'}")

if __name__ == "__main__":
    main()
