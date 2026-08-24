# CLAUDE.md

## 한 줄 정의
믿을 만한 해외 F1 매체를 골라두고, 오늘의 주요 기사 5건을 한국어 3줄 요약 + 원문 링크로 보여준다.

## 검증하려는 가설
한국 F1 팬은 해외 기사를 "믿을 만한 곳에서, 이해 가능한 형태로" 보고 싶어 한다.
→ 측정 지표: 기사별 👍/👎 비율, 원문 링크 클릭률.

## MVP 범위 (확정)

### MUST — 이것만 만든다
| 기능 | 정의 |
|---|---|
| 오늘의 기사 목록 | 하루 5건 고정. 이게 없으면 브리핑 자체가 성립하지 않는다 |
| 한국어 3줄 요약 | 정확히 3문장. 가설의 핵심 |
| 원문 링크 | 모든 기사에 필수. '믿을 만한'을 사용자가 직접 확인하는 유일한 장치 |
| 매체명 표시 | 카드 상단에 노출. 출처 없으면 공신력이 생기지 않는다 |
| 👍 / 👎 버튼 | 기사 단위. 이게 없으면 지표를 못 잰다 |

### NOT — 이번에 만들지 않는다
로그인 / 회원가입 · 검색 · 카테고리 필터 · 즐겨찾기 · 댓글 · 푸시·이메일 발송 · 앱 · 다크모드 · 관리자 페이지 · 과거 기사 아카이브 UI

> 새 기능 요청이 들어오면 먼저 이 표를 근거로 "MVP 범위 밖"이라고 답하고, 필요하면 표를 먼저 수정하게 한다.

## 절대 원칙 (변경 금지)
1. **기사 전문을 저장·번역·재배포하지 않는다.** 3문장 요약 + 원문 링크만 출력한다.
2. **RSS만 사용한다.** 본문 스크래핑, 페이월 우회, User-Agent 위장 금지.
3. **매체명과 원문 URL이 없는 항목은 출력에서 제외한다.**
4. **요약에 없는 사실을 지어내지 않는다.** RSS 요약이 부실하면 제목 기반으로만 처리하고 해당 기사는 후보에서 뺀다.
5. **F1 기사만 노출한다.** Formula E, MotoGP, IndyCar, WEC, BTCC는 제외.

## 소스 (3곳 고정)
- BBC Sport F1
- Autosport (F1)
- The Race

상세 피드 주소와 F1 필터링 규칙은 `docs/sources.md` 참조. 소스 추가·변경은 그 파일만 수정한다.

⚠️ **The Race 피드는 F1 전용이 아니다.** Formula E·MotoGP·IndyCar가 섞여 들어온다.
`filter.py` 에서 URL 경로 또는 카테고리 태그 기준으로 F1만 통과시켜야 한다. 이 필터가 없으면 원칙 5가 깨진다.

## 기술 스택

MVP 원칙: **서버 없음, 프레임워크 없음, 빌드 도구 없음.**

| 영역 | 선택 | 이유 |
|---|---|---|
| 수집·요약 | Python 3.11 스크립트 | 하루 1회 배치. 서버 불필요 |
| 의존성 | `feedparser` | 이것 하나면 끝. LLM 호출은 표준 라이브러리 `urllib` 로 한다. 추가 시 이 표에 근거를 남길 것 |
| LLM | Google Gemini API (`gemini-3.6-flash`) | **무료 티어**. 결제수단 등록 없이 발급된다. SDK 없이 REST(`/v1beta/interactions`) 직접 호출이라 의존성이 늘지 않는다. 분당 요청 한도가 20이라 디버깅 시 주의(운영은 하루 1회라 무관) |
| 실행 | GitHub Actions cron (매일 KST 08:00) | 무료, 별도 인프라 없음 |
| 화면 | 정적 HTML 1개 파일 | React·Next.js 쓰지 않는다. 카드 5개 나열이 전부 |
| 호스팅 | GitHub Pages | |
| 저장소 | Supabase 테이블 1개 (`feedback`) | 👍/👎 기록 **전용**. 기사 데이터는 저장하지 않는다 |

### Supabase를 쓰는 이유와 한계
👍/👎 클릭은 브라우저에서 발생하고 어딘가에 남아야 하므로, 정적 페이지만으로는 불가능하다.
**단, 용도를 이것 하나로 제한한다.**

```sql
create table feedback (
  id          bigserial primary key,
  digest_date date        not null,
  article_id  text        not null,
  vote        smallint    not null,  -- 1 = 👍, -1 = 👎
  created_at  timestamptz default now()
);
```
- 인증 없음. anon key + INSERT만 허용하는 RLS 정책.
- 사용자 식별 없음. 중복 투표 방지는 `localStorage` 로만 처리(완벽하지 않아도 MVP엔 충분).
- **기사 본문·요약·메타데이터를 여기 넣지 않는다.** 기사는 정적 JSON/HTML로 충분하다.

## 디렉터리 구조
```
src/
  fetch.py       # 3개 RSS 수집 → 정규화
  filter.py      # F1 필터 + 중복 제거 + 상위 5건 선정
  summarize.py   # Anthropic API, 3문장 요약
  render.py      # docs/index.html 생성
  main.py
docs/
  sources.md     # 피드 목록 (단일 진실 공급원)
  prompt.md      # 요약 프롬프트
  index.html     # 결과물 = GitHub Pages 루트
  archive/YYYY-MM-DD.html
data/
  seen.json      # 처리 완료 URL 해시
```

## 데이터 계약
```python
{
  "id": str,            # url sha256 앞 16자리. 👍/👎 기록의 키
  "source": str,        # "BBC Sport" | "Autosport" | "The Race"
  "title_en": str,
  "title_ko": str,      # 40자 이내
  "url": str,           # 원문
  "published": str,     # ISO8601 UTC
  "summary_ko": [str, str, str]   # 정확히 3개
}
```
파이프라인 내부 필드 (렌더 전 폐기, 화면에 안 나감):
- `story_key: str` — 같은 사건 묶기용. 요약 단계에서 모델이 붙인다. `docs/prompt.md` 참조.
- `source_priority: int` — 중복 시 남길 매체 결정. `docs/sources.md` 의 표에서 온다.
`summary_ko` 의 길이가 3이 아니면 렌더 단계에서 예외를 발생시킨다.

## 5건 선정 규칙
1. 최근 24시간 내 발행분만 후보. 5건이 안 되면 48시간으로 확장.
2. 뉴스 기사가 아닌 항목(퀴즈·팟캐스트·오디오/영상) 제외. 규칙은 `docs/sources.md`.
3. **1차 중복 제거** — 영문 제목 유사도. 명백한 재탕만 걸러낸다.
4. 후보 10건을 뽑아 **한 번에** 요약한다 (매체당 최대 4건).
5. **2차 중복 제거** — 요약 시 모델이 붙인 `story_key` 로 같은 사건을 묶는다.
6. 한 매체가 3건을 초과하지 않도록 조정. 묶인 사건의 대표는 **상한에 걸리지 않은 매체 중** 우선순위(BBC > Autosport > The Race)가 높은 기사로 고른다.
7. 그래도 부족하면 부족한 채로 낸다. **빈칸을 채우려 억지 기사를 넣지 않는다.**

> **왜 2단계인가.** 영문 제목만으로는 같은 사건을 못 잡는다. BBC `Norris beats Antonelli to claim Dutch GP win` 과 The Race `F1 Dutch GP race results` 가 나란히 노출된 적이 있다.
> 한국어 요약 유사도로도 실패했다(실측 Jaccard 0.00 — 두 매체가 같은 사건을 완전히 다른 어휘로 쓴다).
> 그래서 사건 식별은 모델에게 맡긴다. **LLM 호출은 여전히 1회다.**
>
> **왜 대표를 우선순위로만 고르면 안 되는가.** BBC 가 모든 묶음을 이겨서 BBC 로 쏠리고, 그다음 상한 3건에 걸려 최종이 4건으로 떨어진다. 실제로 발생했다.

## 화면에 반드시 들어갈 문구 (Disclaimer)
푸터에 아래 내용을 그대로 노출한다. 문구 수정은 이 파일에서 먼저 한다.

> **안내**
> - 본 서비스는 Formula 1, FIA, Formula One World Championship Limited 및 각 매체와 아무런 제휴 관계가 없는 비공식·개인 프로젝트입니다.
> - F1®, FORMULA 1® 등은 Formula One Licensing B.V.의 등록 상표입니다.
> - 모든 기사의 저작권은 각 매체에 있습니다. 본 서비스는 원문을 제공하지 않으며, AI가 생성한 짧은 한국어 요약과 원문 링크만 제공합니다.
> - 요약은 AI가 자동 생성한 것으로 오역·오류가 있을 수 있습니다. **정확한 내용은 반드시 원문을 확인해 주세요.**
> - 게재 중단을 원하는 매체는 (연락처)로 알려주시면 즉시 조치하겠습니다.

각 기사 카드에는 매체명과 "원문 보기" 링크를 항상 함께 노출한다.

## 코딩 규칙
- 프롬프트는 `docs/prompt.md` 에서 읽어온다. 코드에 하드코딩 금지.
- 피드 URL은 `docs/sources.md` 에서 읽어온다. 코드에 하드코딩 금지.
- API 키·Supabase 키는 환경변수. 커밋·로그에 남기지 않는다. 로컬은 `.env`(gitignore 대상), CI 는 GitHub Secrets.
- LLM 호출은 기사별이 아니라 **5건 한 번에** 묶어서 1회.
- 한 소스가 실패해도 나머지로 진행한다.
- 새 라이브러리·새 서비스를 추가하려면 "기술 스택" 표에 행을 추가하고 이유를 적는다. 이유를 못 적으면 추가하지 않는다.

## 레퍼런스
- 출력 형식: `docs/reference/sample-output.html` — 렌더 작업 전 반드시 읽을 것
- RSS 실제 구조: `docs/reference/raw-*.xml` — 파서 수정 시 참고
