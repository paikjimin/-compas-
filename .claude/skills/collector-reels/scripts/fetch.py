#!/usr/bin/env python3
"""YouTube 소스 다운로드: work/<id>/source.mp4 (+ info.json, 자동자막 vtt)."""
import argparse, json, pathlib, subprocess, sys

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--work", default="work")
    a = ap.parse_args()
    for url in a.urls:
        vid = subprocess.run(["yt-dlp", "--print", "id", "--skip-download", url],
                             capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1]
        d = pathlib.Path(a.work) / vid
        d.mkdir(parents=True, exist_ok=True)
        if (d / "source.mp4").exists():
            print(f"[skip] {vid}"); continue
        subprocess.run([
            "yt-dlp", "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]/b",
            "--merge-output-format", "mp4", "-o", str(d / "source.%(ext)s"),
            "--write-info-json", "--write-subs", "--write-auto-subs",
            "--sub-langs", "ko.*,ko", "--sub-format", "vtt", "--ignore-errors", url], check=False)
        if not (d / "source.mp4").exists():
            sys.exit(f"다운로드 실패: {url}")
        info = d / "source.info.json"
        if info.exists():
            j = json.loads(info.read_text())
            (d / "meta.json").write_text(json.dumps({k: j.get(k) for k in
                ("id", "title", "channel", "duration", "webpage_url", "description")}, ensure_ascii=False, indent=2))
        print(f"[ok] {vid} -> {d}")

if __name__ == "__main__":
    main()
