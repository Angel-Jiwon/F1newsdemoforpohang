"""Gemini API 로 3문장 한국어 요약.

프롬프트는 docs/prompt.md 에서 읽는다 (코딩 규칙).
LLM 호출은 기사별이 아니라 5건을 한 번에 묶어 1회만 한다.

SDK 를 쓰지 않고 표준 라이브러리 urllib 로 REST 를 직접 호출한다.
호출이 하루 1회 1건이라 SDK 의존성을 늘릴 이유가 없다.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPT_MD = ROOT / "docs" / "prompt.md"

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
# 무료 티어 모델. 실제 5건 페이로드로 검증한 것은 3.6-flash 다.
# GEMINI_MODEL 로 바꿀 수 있다 (gemini-3.7-flash 도 무료 티어).
# ⚠️ gemini-2.5-flash 는 신규 사용자에게 폐기됐다(404).
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
TIMEOUT_SECONDS = 120
# 하루 1회 도는 배치다. 일시적 과부하(500/503)나 레이트리밋(429)에 그냥 죽으면
# 그날 브리핑이 통째로 빈다. 몇 번은 기다렸다 다시 친다.
RETRY_STATUSES = (429, 500, 502, 503, 504)
MAX_ATTEMPTS = 4
BACKOFF_SECONDS = (5, 20, 60)

# response_format(구조화 출력)은 쓰지 않는다.
# 이 엔드포인트에 붙이면 500 이 돌아온다(2026-08-24 확인). 출력 형태는
# docs/prompt.md 의 지시문으로 잡고, 코드펜스는 _parse() 에서 걷어낸다.


def load_prompt(path: Path = PROMPT_MD) -> tuple[str, str]:
    """docs/prompt.md 의 ## SYSTEM / ## USER_TEMPLATE 블록을 그대로 읽어온다."""
    text = path.read_text(encoding="utf-8")
    blocks: dict[str, str] = {}
    for name in ("SYSTEM", "USER_TEMPLATE"):
        match = re.search(rf"^## {name}\s*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
        if not match:
            raise ValueError(f"{path} 에 '## {name}' 블록이 없다")
        blocks[name] = match.group(1).strip()
    return blocks["SYSTEM"], blocks["USER_TEMPLATE"]


def _payload(articles: list[dict]) -> str:
    """LLM 에 넘길 최소 입력. 기사 전문은 애초에 갖고 있지 않다."""
    return json.dumps(
        [
            {
                "id": a["id"],
                "source": a["source"],
                "title": a["title_en"],
                "rss_summary": a["summary_en"],
            }
            for a in articles
        ],
        ensure_ascii=False,
        indent=2,
    )


def _extract_text(response: dict) -> str:
    """생성된 텍스트를 꺼낸다.

    실제 REST 응답은 steps[] 안에 thought / model_output 이 나뉘어 온다.
    thought(내부 추론)는 버리고 model_output 의 text 만 이어붙인다.
    """
    text = response.get("output_text")
    if isinstance(text, str) and text.strip():
        return text

    chunks = [
        part.get("text", "")
        for step in response.get("steps", [])
        if step.get("type") == "model_output"
        for part in step.get("content", [])
        if part.get("type") == "text"
    ]
    if any(c.strip() for c in chunks):
        return "".join(chunks)

    raise ValueError(f"응답에서 생성 텍스트를 찾지 못했다: {json.dumps(response)[:400]}")


def _parse(text: str) -> list[dict]:
    """JSON 만 오도록 지시했지만 코드블록이 붙어 오는 경우를 걷어낸다."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.M)
    return json.loads(cleaned)


def _mock(articles: list[dict]) -> list[dict]:
    """API 키가 없을 때 쓰는 자리표시자.

    원칙 4에 따라 사실을 지어내지 않는다. 요약 자리에 목데이터임을 그대로 적는다.
    """
    return [
        {
            "id": a["id"],
            "title_ko": f"[목데이터] {a['title_en']}"[:40],
            "summary_ko": [
                "[목데이터] 아직 실제 요약이 생성되지 않았다.",
                "GEMINI_API_KEY 를 설정하고 다시 실행하면 이 자리에 3문장 요약이 들어간다.",
                f"원문 제목: {a['title_en']}",
            ],
            "story_key": f"mock-{a['id']}",
            "insufficient": False,
        }
        for a in articles
    ]


def _call_api(system: str, user: str, api_key: str) -> str:
    body = json.dumps(
        {
            "model": MODEL,
            "system_instruction": system,
            "input": user,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )

    for attempt in range(MAX_ATTEMPTS):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return _extract_text(json.loads(response.read().decode("utf-8")))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            retriable = exc.code in RETRY_STATUSES and attempt < MAX_ATTEMPTS - 1
            if not retriable:
                raise RuntimeError(f"Gemini API {exc.code}: {detail}") from exc
            wait = BACKOFF_SECONDS[attempt]
            print(
                f"  ! {exc.code} 응답 — {wait}초 후 재시도 "
                f"({attempt + 2}/{MAX_ATTEMPTS})",
                file=sys.stderr,
            )
            time.sleep(wait)
        except urllib.error.URLError as exc:
            if attempt >= MAX_ATTEMPTS - 1:
                raise RuntimeError(f"Gemini API 연결 실패: {exc.reason}") from exc
            wait = BACKOFF_SECONDS[attempt]
            print(f"  ! 연결 실패 — {wait}초 후 재시도", file=sys.stderr)
            time.sleep(wait)

    raise RuntimeError("Gemini API 재시도 한도 초과")


def summarize(articles: list[dict], use_mock: bool | None = None) -> list[dict]:
    """기사 목록에 title_ko / summary_ko 를 채워 반환한다.

    요약이 부실(insufficient)하거나 3문장이 아닌 기사는 결과에서 뺀다.
    """
    if not articles:
        return []

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if use_mock is None:
        use_mock = not api_key

    if use_mock:
        print("  ! GEMINI_API_KEY 없음 — 목데이터로 진행", file=sys.stderr)
        results = _mock(articles)
    else:
        system, user_template = load_prompt()
        user = user_template.format(count=len(articles), articles_json=_payload(articles))
        print(f"  · LLM 호출 1회 ({MODEL}, {len(articles)}건 묶음)")
        results = _parse(_call_api(system, user, api_key))

    by_id = {r.get("id"): r for r in results}
    summarized: list[dict] = []
    for article in articles:
        result = by_id.get(article["id"])
        if result is None:
            print(f"  ! 응답 누락, 제외: {article['title_en'][:50]}", file=sys.stderr)
            continue
        if result.get("insufficient"):
            print(f"  ! 정보 부족, 제외: {article['title_en'][:50]}", file=sys.stderr)
            continue

        summary = result.get("summary_ko") or []
        if len(summary) != 3:
            print(
                f"  ! 요약이 {len(summary)}문장이라 제외: {article['title_en'][:50]}",
                file=sys.stderr,
            )
            continue

        summarized.append(
            {
                "id": article["id"],
                "source": article["source"],
                "source_priority": article["source_priority"],
                "story_key": result.get("story_key") or "",
                "title_en": article["title_en"],
                "title_ko": (result.get("title_ko") or article["title_en"])[:40],
                "url": article["url"],
                "published": article["published"],
                "summary_ko": summary,
            }
        )
    return summarized
