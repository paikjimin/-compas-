---
name: collector-reels
description: 유튜브 영상 소스에서 주요 장면을 자동 추출해 제목·자막을 입힌 9:16 인스타그램 릴스(컬렉터 이야기)를 만든다. "릴스 만들어줘", "영상 소스로 릴스", "컬렉터 릴스" 등 유튜브 링크와 함께 릴스 제작을 요청할 때 사용.
---

# 컬렉터 릴스 자동 제작

유튜브 링크 → 다운로드 → 전사/장면분석 → (Claude가) 하이라이트 선정·제목·자막 작성 → 9:16 mp4 렌더.

스크립트 경로: `S=.claude/skills/collector-reels/scripts`
작업 폴더: `reels/work/<영상ID>/`, 결과물: `reels/out/`

## 0. 준비 (최초 1회)
```bash
pip install yt-dlp faster-whisper
# ffmpeg(libass 포함) + 한글 폰트(Pretendard / Noto Sans CJK KR / 나눔고딕 중 하나) 필요
```

## 1. 다운로드
```bash
python $S/fetch.py <URL1> <URL2> ... --work reels/work
```

## 1-1. 권리 확인 (필수 · 렌더 차단 게이트)
```bash
python $S/rights.py init  --work reels/work   # reels/rights.json 생성/갱신 (유튜브 CC BY 영상은 자동 표시)
python $S/rights.py check --work reels/work   # ⛔ 항목이 있으면 render.py가 최종본을 만들지 않음
```
소스마다 `reels/rights.json`에 다음을 채운다 (Claude는 사용자 확인 없이 승인값을 임의로 채우지 않는다):
- `basis`: `permission`(원작자 허락) / `cc-by`(유튜브 CC BY 표시) / `own`(직접 촬영·본인 채널). 그 외는 렌더 불가
- `evidence`: 허락 메일·DM 캡처 경로나 날짜 / `scope`, `expires`: 허락 범위·기한(만료 시 차단)
- `credit`: 캡션에 자동으로 붙는 출처 문구
- `portrait_ok`: 출연 컬렉터 초상 사용 동의 확인 / `music_ok`: 영상 속 배경음악 문제 없음(제거·권리 확인)

미확인 소스는:
1. `permission_request.md` 템플릿으로 원작 채널에 허락 요청 메일/DM 초안을 작성해 사용자에게 준다.
2. 허락 요청에 첨부하거나 내부 검토용으로 `render.py --preview`로 시안을 만든다. 시안에는 `PREVIEW · 게시 불가` 워터마크가 붙고 파일명에 `_PREVIEW`가 들어간다.
- 오래된 영상이어도, 출처를 표기해도 허락을 대신하지 않는다. 해외 영상도 똑같이 보호받는다. 권리 확인을 피하는 방법은 안내하지 않는다.

## 2. 분석
```bash
python $S/analyze.py --work reels/work          # --model medium 으로 전사 정확도↑
```
영상마다 `analysis.md`(장면 전환 시각 + 타임스탬프 전사), `frames/`(10초 간격 키프레임) 생성.

## 3. 하이라이트 선정 & 기획 (Claude가 직접 수행)
1. 각 `analysis.md`를 읽고, 필요하면 `frames/*.jpg` 몇 장을 열어 화면(컬렉션 진열, 인물, 아이템 클로즈업)을 확인한다.
2. **컬렉터 이야기** 관점에서 릴스 1개당 다음 구조로 고른다 (총 30~60초, 클립 3~6개):
   - **훅(0~3초)**: 가장 강한 한 마디/수치/반전 ("집 한 채 값", "40년", "전 세계 3개뿐" 등)
   - **사연**: 수집을 시작한 계기, 첫 아이템
   - **하이라이트 아이템**: 가장 비싸거나 희귀한 것, 시각적으로 압도적인 진열 장면
   - **마무리**: 철학/명언 한 줄 ("모으는 게 아니라 지키는 거예요")
3. 클립 경계는 문장 단위로 끊는다 (전사 segment의 start/end 사용, 장면 전환 시각과 가까우면 그쪽에 맞춤). 클립당 3~15초.
4. 자막은 전사를 그대로 쓰지 말고 **다듬는다**: 오인식 교정, 군더더기(음, 그, 이제) 제거, 한 줄 16자 내외, 한 자막 1~3초.
5. 제목: 15자 내외 2줄 이내, 핵심 단어는 `[ ]`로 감싸면 노란색 강조. 예: `"월급 전부 [레고]에\n쏟은 남자"`
6. `reels/plans/reel_XX.json` 작성 (영상 소스당 1개 이상, 또는 여러 소스 혼합 가능):
```json
{
  "title": "40년 모은 [시계]\n전부 공개합니다",
  "output": "reel_01.mp4",
  "layout": "blur",
  "caption": "인스타 본문 캡션 2~3줄\n\n#컬렉터 #수집 #컬렉션 ...",
  "clips": [
    {"source": "E2JfJBmGa7s", "start": 63.2, "end": 71.8,
     "subtitles": [
       {"start": 63.2, "end": 65.9, "text": "처음엔 그냥 하나였어요"},
       {"start": 66.0, "end": 71.8, "text": "근데 40년이 지나니까\n이렇게 됐네요"}
     ]}
  ]
}
```
   - `subtitles` 시간은 **원본 영상 기준 초**. 생략 시 전사 자동 사용.
   - `layout`: `blur`(가로 영상 전체 + 흐린 배경, 기본) / `crop`(중앙 크롭, 인물 클로즈업에 적합). 클립별 지정 가능.
   - 선택: `"style": {"title_size": 78, "title_y": 230, "sub_size": 64, "sub_y": 380, "wrap": 16}`, `"font": "Pretendard"`

## 4. 렌더
```bash
python $S/render.py reels/plans/reel_01.json --work reels/work --out reels/out            # 권리 확인 통과 시에만
python $S/render.py reels/plans/reel_01.json --work reels/work --out reels/out --preview  # 워터마크 시안
```
결과: `reels/out/reel_01.mp4` (1080x1920, 30fps), `.ass`(자막 원본, 수정 후 재번인 가능), `.txt`(캡션 + `credit` 출처 자동 포함).

## 5. 검수
렌더 후 `ffmpeg -ss <t> -i out.mp4 -frames:v 1 check.jpg`로 2~3컷 뽑아 제목/자막 위치·잘림을 확인하고, 문제 있으면 plan 수정 후 재렌더.

## 주의
- 기본 요청 시 소스 영상 수만큼 릴스를 만들고, 각 릴스의 제목·선정 이유·권리 상태(✅/⛔)를 표로 요약해 보고한다.
