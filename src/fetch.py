"""3개 RSS 수집 → 정규화.

피드 URL은 docs/sources.md 표에서만 읽는다 (코딩 규칙).
"""
from __future__ import annotations

import hashlib
import html
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import feedparser

ROOT = Path(__file__).resolve().parent.parent
SOURCES_MD = ROOT / "docs" / "sources.md"

# 추적 파라미터. 제거해야 id(url 해시)가 안정적이다.
TRACKING_PREFIXES = ("utm_", "at_")


@dataclass(frozen=True)
class Source:
    name: str
    priority: int
    f1_only: bool
    rss_url: str


def _clean_cell(cell: str) -> str:
    """마크다운 강조(**no**)·백틱을 걷어낸다."""
    return cell.strip().strip("*`").strip()


def load_sources(path: Path = SOURCES_MD) -> list[Source]:
    """docs/sources.md 의 표를 파싱한다. 단일 진실 공급원."""
    sources: list[Source] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [_clean_cell(c) for c in line.strip("|").split("|")]
        if len(cells) != 5:
            continue
        enabled, name, priority, f1_only, rss_url = cells
        if enabled.lower() != "yes":
            continue  # 헤더행·구분행·비활성 소스
        if not rss_url.startswith("http"):
            raise ValueError(f"{name}: rss_url 이 아직 자리표시자다 → {rss_url!r}")
        sources.append(
            Source(
                name=name,
                priority=int(priority),
                f1_only=(f1_only.lower() == "yes"),
                rss_url=rss_url,
            )
        )
    if not sources:
        raise ValueError(f"{path} 에서 활성 소스를 하나도 못 읽었다")
    return sources


def canonical_url(url: str) -> str:
    """추적 파라미터를 떼어낸 정규 URL."""
    parts = urlsplit(url)
    kept = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith(TRACKING_PREFIXES)
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept), ""))


def article_id(url: str) -> str:
    """데이터 계약: url sha256 앞 16자리. 👍/👎 기록의 키."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def strip_html(raw: str) -> str:
    """RSS 요약문에서 태그와 'Keep reading' 꼬리를 제거한다."""
    text = re.sub(r"<a\b[^>]*class=['\"]more['\"].*?</a>", " ", raw, flags=re.I | re.S)
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = text.replace(" ", " ")
    return re.sub(r"\s+", " ", text).strip()


def _published(entry) -> str | None:
    """ISO8601 UTC 문자열. 날짜를 못 읽으면 None (해당 기사는 버린다)."""
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    dt = datetime(*parsed[:6], tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _categories(entry) -> list[str]:
    return [t.get("term", "") for t in entry.get("tags", []) or [] if t.get("term")]


def fetch_source(source: Source) -> list[dict]:
    """한 소스를 수집해 정규화한다. 실패해도 예외를 올리지 않는다."""
    feed = feedparser.parse(source.rss_url)
    if getattr(feed, "bozo", False) and not feed.entries:
        print(f"  ! {source.name}: 피드 파싱 실패 — {feed.get('bozo_exception')}", file=sys.stderr)
        return []

    articles: list[dict] = []
    for entry in feed.entries:
        title = (entry.get("title") or "").strip()
        link = entry.get("link") or ""
        published = _published(entry)

        # 원칙 3: 매체명과 원문 URL이 없는 항목은 제외.
        if not title or not link or not published:
            continue

        url = canonical_url(link)
        # 원칙 1: content:encoded(전문)는 절대 읽지 않는다. description 만 쓴다.
        summary_en = strip_html(entry.get("summary", "") or "")

        articles.append(
            {
                "id": article_id(url),
                "source": source.name,
                "source_priority": source.priority,
                "source_f1_only": source.f1_only,
                "title_en": title,
                "url": url,
                "published": published,
                "summary_en": summary_en,
                "categories": _categories(entry),
            }
        )
    return articles


def fetch_all(sources: list[Source] | None = None) -> list[dict]:
    """전체 수집. 한 소스가 실패해도 나머지로 진행한다 (코딩 규칙)."""
    sources = sources or load_sources()
    collected: list[dict] = []
    for source in sources:
        try:
            articles = fetch_source(source)
        except Exception as exc:  # 네트워크·파서 오류 전부
            print(f"  ! {source.name}: 수집 실패 — {exc}", file=sys.stderr)
            continue
        print(f"  · {source.name}: {len(articles)}건")
        collected.extend(articles)
    return collected


if __name__ == "__main__":
    for a in fetch_all():
        print(a["source"], "|", a["published"], "|", a["title_en"][:70])
