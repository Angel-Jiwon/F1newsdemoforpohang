# 소스 목록

수집 대상의 **단일 진실 공급원**. 코드는 이 표를 파싱해 동작한다.

## 표

| enabled | source | priority | f1_only | rss_url |
|---|---|---|---|---|
| yes | BBC Sport | 3 | yes | https://feeds.bbci.co.uk/sport/formula1/rss.xml |
| yes | Autosport | 2 | yes | https://www.autosport.com/rss/f1/news/ |
| yes | The Race | 1 | **no** | https://www.the-race.com/rss/ |

- `priority` : 중복 기사 제거 시 남길 매체 결정 (높을수록 우선).
- `f1_only` : `no` 인 소스는 반드시 F1 필터를 통과시켜야 한다.

## 피드 주소 검증 (완료)

세 곳 모두 200 응답 확인. 원본 XML은 `docs/reference/raw-<source>.xml` 에 저장.

- **BBC Sport F1** — `https://feeds.bbci.co.uk/sport/formula1/rss.xml`
  F1 전용 피드. 별도 필터 불필요.
  `<item>` 필드: `title` `description` `link` `guid` `pubDate` `media:thumbnail`.
  ⚠️ `link` 에 `?at_medium=RSS&at_campaign=rss` 추적 파라미터가 붙는다. 제거 후 사용.
- **Autosport (F1 뉴스)** — `https://www.autosport.com/rss/f1/news/`
  F1 전용 피드. `<category>Formula 1</category>` 태그도 함께 온다.
  ⚠️ `description` 에 `<br>` 과 "Keep reading" `<a>` 가 섞여 있다. 태그 제거 후 사용.
  ⚠️ `link` 에 `utm_*` 파라미터가 붙는다. 제거 후 사용.
  (`https://www.autosport.com/rss/feed/f1` 도 같은 곳으로 301 리다이렉트된다.)
- **The Race** — `https://www.the-race.com/rss/`
  F1 전용 피드가 아니다. F1 외 **Formula E, MotoGP, IndyCar, 모터스포츠 비즈니스**가 섞여 들어온다.
  다행히 F1 기사는 URL 경로 `/formula-1/` 과 `<category>Formula 1</category>` 를 모두 갖는다. 아래 필터 규칙 1·2로 판정 가능.
  🚫 **`<content:encoded>` 에 기사 전문이 실려 온다. 이 필드는 읽지 않는다.** (원칙 1)
  요약 입력으로는 `<description>` 만 쓴다.

검증 방법:
```bash
curl -sI "<URL>" | head -1        # 200 확인
curl -s  "<URL>" | head -60       # <item> 구조와 필드 확인
```
확인한 원본 XML은 `docs/reference/raw-<source>.xml` 로 저장해 둔다.

## F1 필터 규칙

`f1_only: no` 인 소스는 아래 순서로 판정한다.

1. **URL 경로** — `/f1/`, `/formula-1/`, `/formula1/` 포함 시 통과 (가장 신뢰도 높음)
2. **RSS 카테고리 태그** — `<category>` 값이 Formula 1 계열이면 통과
3. **제외 키워드** — 위 둘로 판정 불가 시, 아래가 제목/요약에 있으면 탈락
   `Formula E`, `MotoGP`, `IndyCar`, `WEC`, `BTCC`, `NASCAR`, `WRC`, `Le Mans`, `F2`, `F3`
4. 그래도 판정 불가하면 **제외한다.** (통과시키지 않는다 — 오탐이 누락보다 나쁘다)

## 기사 아닌 항목 제외

F1 항목이어도 뉴스 기사가 아니면 3문장 요약이 성립하지 않는다. 모든 소스에 공통 적용한다.

| 판정 | 기준 | 예 |
|---|---|---|
| 키워드 | 제목에 `quiz`, `podcast` 포함 | `Five in Five: Formula 1 quiz No 1` |
| 제목 전체 일치 | `f1: chequered flag` | BBC 팟캐스트 프로그램 |
| URL 경로 | `/av/` 포함 (BBC 오디오·영상) | |

⚠️ `chequered flag` 를 **부분 일치 키워드로 쓰면 안 된다.** "takes the chequered flag" 같은 실제 경기 기사까지 걸린다.
프로그램명은 반드시 제목 전체 일치로만 판정한다.

구현은 `filter.py` 의 `is_article()`. 위 표를 고치면 그 함수도 같이 고친다.

## 검증 로그
| 날짜 | 내용 |
|---|---|
| 2026-08-23 | 최초 등록. BBC만 주소 확인 완료 |
| 2026-08-23 | Autosport·The Race 주소 확정(200 확인), raw XML 3건 저장. The Race 는 `content:encoded` 에 전문이 실려 오므로 `description` 만 사용하기로 결정 |
| 2026-08-23 | BBC 피드에 퀴즈·팟캐스트가 하루 8건가량 섞여 들어와 "기사 아닌 항목 제외" 규칙 추가 |

## 소스를 늘리지 않는 이유
3곳이면 하루 5건을 채우기에 충분하다. 소스가 늘면 중복 기사 판정과 LLM 비용이 함께 늘어난다.
추가는 "5건을 못 채우는 날이 반복될 때"에만 검토한다.
