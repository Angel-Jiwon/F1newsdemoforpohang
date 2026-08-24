"""F1 필터 + 중복 제거 + 상위 5건 선정.

판정 규칙의 원문은 docs/sources.md 의 "F1 필터 규칙" 절이다.
아래 상수를 고칠 때는 그 문서도 함께 고친다.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

# 규칙 1: URL 경로
F1_URL_PATHS = ("/f1/", "/formula-1/", "/formula1/")
# 규칙 2: RSS 카테고리
F1_CATEGORIES = ("formula 1", "formula1", "f1")
# 규칙 3: 제외 키워드
EXCLUDE_KEYWORDS = (
    "formula e", "motogp", "indycar", "wec", "btcc",
    "nascar", "wrc", "le mans", "f2", "f3",
)

# 기사가 아닌 항목(퀴즈·팟캐스트·오디오/영상)은 3문장 요약이 성립하지 않아 제외한다.
# 규칙 원문은 docs/sources.md 의 "기사 아닌 항목 제외" 절.
NON_ARTICLE_KEYWORDS = ("quiz", "podcast")
# "chequered flag" 는 일반 표현이라 키워드로 쓰면 안 된다("...takes the chequered flag").
# BBC 팟캐스트 프로그램명만 제목 전체 일치로 걸러낸다.
NON_ARTICLE_TITLES = ("f1: chequered flag",)
# BBC 의 오디오·영상 페이지 경로.
NON_ARTICLE_URL_PATHS = ("/av/",)

TARGET_COUNT = 5
MAX_PER_SOURCE = 3
# 요약 후 같은 사건이 합쳐지면 5건에 못 미친다. 넉넉히 후보를 뽑아 한 번에 요약하고
# 합친 뒤 5건을 고른다. LLM 호출은 여전히 1회다.
CANDIDATE_COUNT = 10
# 최종 상한(MAX_PER_SOURCE)보다 1 크게 둔다. 같은 사건으로 한 건이 합쳐져 빠져도
# 그 매체에서 3건이 남는다. 5로 두면 BBC 가 후보를 독식해 최종이 4건으로 떨어진다.
CANDIDATE_PER_SOURCE = MAX_PER_SOURCE + 1
PRIMARY_WINDOW_HOURS = 24
FALLBACK_WINDOW_HOURS = 48

# 제목 유사도 임계치. 두 지표 중 하나만 넘어도 같은 사건으로 본다.
SEQUENCE_THRESHOLD = 0.62
JACCARD_THRESHOLD = 0.5

# 유사도 계산에서 뺄 흔한 단어. 남기면 무관한 기사끼리 붙는다.
STOPWORDS = frozenset(
    "a an the of in on at to for and or with as after before from by is was "
    "his her its their f1 formula gp grand prix".split()
)


def is_f1(article: dict) -> bool:
    """docs/sources.md 의 규칙 1→2→3 순으로 판정. 판정 불가면 제외한다."""
    if article["source_f1_only"]:
        return True  # F1 전용 피드

    url = article["url"].lower()
    if any(path in url for path in F1_URL_PATHS):
        return True

    categories = [c.strip().lower() for c in article["categories"]]
    if any(c in F1_CATEGORIES for c in categories):
        return True

    haystack = f"{article['title_en']} {article['summary_en']}".lower()
    if any(kw in haystack for kw in EXCLUDE_KEYWORDS):
        return False

    # 규칙 4: 그래도 판정 불가하면 제외한다. 오탐이 누락보다 나쁘다.
    return False


def is_article(article: dict) -> bool:
    """뉴스 기사인지 판정한다. 퀴즈·팟캐스트·오디오/영상 페이지는 제외."""
    title = article["title_en"].strip().lower()
    if title in NON_ARTICLE_TITLES:
        return False
    if any(kw in title for kw in NON_ARTICLE_KEYWORDS):
        return False
    if any(path in article["url"].lower() for path in NON_ARTICLE_URL_PATHS):
        return False
    return True


def _within(article: dict, now: datetime, hours: int) -> bool:
    published = datetime.strptime(article["published"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    return now - timedelta(hours=hours) <= published <= now + timedelta(hours=1)


def _tokens(title: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", title.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


def _same_story(a: dict, b: dict) -> bool:
    """동일 사건 판정. 제목 유사도 기준."""
    ta, tb = _tokens(a["title_en"]), _tokens(b["title_en"])
    if ta and tb:
        jaccard = len(ta & tb) / len(ta | tb)
        if jaccard >= JACCARD_THRESHOLD:
            return True
    ratio = SequenceMatcher(None, a["title_en"].lower(), b["title_en"].lower()).ratio()
    return ratio >= SEQUENCE_THRESHOLD


def deduplicate(articles: list[dict]) -> list[dict]:
    """동일 사건 묶음에서 매체 우선순위(BBC > Autosport > The Race)가 높은 쪽을 남긴다."""
    kept: list[dict] = []
    for article in sorted(articles, key=lambda a: (-a["source_priority"], a["published"])):
        duplicate_of = next((k for k in kept if _same_story(k, article)), None)
        if duplicate_of is None:
            kept.append(article)
        else:
            print(
                f"  · 중복 제거: [{article['source']}] {article['title_en'][:50]}"
                f"  ← [{duplicate_of['source']}] {duplicate_of['title_en'][:50]}"
            )
    return kept


def _pick(articles: list[dict], count: int, per_source_cap: int) -> list[dict]:
    """최신순으로 고르되 한 매체가 상한을 넘지 않게 한다."""
    picked: list[dict] = []
    per_source: dict[str, int] = {}
    for article in sorted(articles, key=lambda a: a["published"], reverse=True):
        if len(picked) >= count:
            break
        if per_source.get(article["source"], 0) >= per_source_cap:
            continue
        picked.append(article)
        per_source[article["source"]] = per_source.get(article["source"], 0) + 1
    return picked


def finalize(summarized: list[dict]) -> list[dict]:
    """요약 결과에서 같은 사건을 합치고 최종 5건을 고른다.

    영문 제목 유사도만으로는 같은 사건을 못 잡는다. 실제로 BBC "Norris beats
    Antonelli to claim Dutch GP win" 과 The Race "F1 Dutch GP race results" 가
    나란히 노출됐다. 그래서 요약 단계에서 모델이 붙인 story_key 로 다시 묶는다.

    묶은 뒤 대표를 고를 때 매체 우선순위만 보면 BBC 가 모든 그룹을 이겨 버린다.
    그러면 BBC 가 상한 3건에 걸려 최종이 5건에 못 미친다. 그래서 대표는
    "아직 상한에 안 걸린 매체" 중 우선순위가 가장 높은 기사로 고른다.
    """
    groups: dict[str, list[dict]] = {}
    for article in summarized:
        # story_key 가 없으면 합치지 않는다. id 는 고유하므로 단독 그룹이 된다.
        key = article.get("story_key") or f"__{article['id']}"
        groups.setdefault(key, []).append(article)

    for key, members in groups.items():
        if len(members) > 1:
            titles = " / ".join(f"[{m['source']}] {m['title_ko'][:24]}" for m in members)
            print(f"  · 같은 사건 묶음[{key}]: {titles}")

    # 그룹을 최신순으로 훑으며 상한에 걸리지 않는 대표를 하나씩 뽑는다.
    ordered = sorted(
        groups.values(),
        key=lambda members: max(m["published"] for m in members),
        reverse=True,
    )
    picked: list[dict] = []
    per_source: dict[str, int] = {}
    for members in ordered:
        if len(picked) >= TARGET_COUNT:
            break
        for member in sorted(members, key=lambda m: -m["source_priority"]):
            if per_source.get(member["source"], 0) < MAX_PER_SOURCE:
                picked.append(member)
                per_source[member["source"]] = per_source.get(member["source"], 0) + 1
                break
        else:
            print(f"  ! 모든 매체가 상한이라 사건 하나를 건너뛴다")

    return sorted(picked, key=lambda a: a["published"], reverse=True)


def select(articles: list[dict], now: datetime | None = None) -> list[dict]:
    """요약에 넘길 후보를 고른다. 최종 5건 확정은 finalize() 에서 한다."""
    now = now or datetime.now(timezone.utc)

    f1_articles = [a for a in articles if is_f1(a)]
    print(f"  · F1 필터 통과: {len(f1_articles)}/{len(articles)}건")

    before = len(f1_articles)
    f1_articles = [a for a in f1_articles if is_article(a)]
    if before != len(f1_articles):
        print(f"  · 기사 아닌 항목 제외(퀴즈·팟캐스트·AV): {before - len(f1_articles)}건")

    for hours in (PRIMARY_WINDOW_HOURS, FALLBACK_WINDOW_HOURS):
        recent = [a for a in f1_articles if _within(a, now, hours)]
        print(f"  · 최근 {hours}시간: {len(recent)}건")
        picked = _pick(deduplicate(recent), CANDIDATE_COUNT, CANDIDATE_PER_SOURCE)
        if len(picked) >= CANDIDATE_COUNT:
            return picked

    # 48시간으로도 부족하면 부족한 채로 낸다. 억지로 채우지 않는다.
    print(f"  · 후보 {len(picked)}건 (목표 {CANDIDATE_COUNT}건)")
    return picked
