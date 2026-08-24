"""수집 → 필터 → 요약 → 렌더 전체 실행.

    python src/main.py            # ANTHROPIC_API_KEY 있으면 실제 요약, 없으면 목데이터
    python src/main.py --mock     # 키가 있어도 목데이터로
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fetch import fetch_all
from filter import finalize, select
from render import render
from summarize import summarize

ROOT = Path(__file__).resolve().parent.parent
SEEN = ROOT / "data" / "seen.json"
KST = timezone(timedelta(hours=9))


def load_env() -> None:
    """저장소 루트의 .env 를 읽어 환경변수로 올린다. 이미 설정된 값은 덮어쓰지 않는다.

    .env 는 .gitignore 에 있다. 라이브러리를 늘리지 않으려고 직접 읽는다.
    """
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def load_seen() -> dict[str, str]:
    """{article_id: 처음 내보낸 digest_date}"""
    if not SEEN.exists():
        return {}
    return json.loads(SEEN.read_text(encoding="utf-8"))


def save_seen(seen: dict[str, str], articles: list[dict], digest_date: str) -> None:
    for article in articles:
        seen.setdefault(article["id"], digest_date)
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(json.dumps(seen, ensure_ascii=False, indent=2), encoding="utf-8")


def main(use_mock: bool | None = None) -> int:
    load_env()
    digest_date = datetime.now(KST).strftime("%Y-%m-%d")
    seen = load_seen()

    print("[1/5] 수집")
    articles = fetch_all()

    # 이전 날짜에 이미 내보낸 기사는 제외한다. 같은 날 재실행은 그대로 재현되도록 오늘 것은 남긴다.
    fresh = [a for a in articles if seen.get(a["id"], digest_date) == digest_date]
    if len(fresh) < len(articles):
        print(f"  · 지난 브리핑에 나간 기사 제외: {len(articles) - len(fresh)}건")

    print("[2/5] 필터 · 후보 선정")
    picked = select(fresh)
    if not picked:
        print("  ! 조건을 만족하는 기사가 없다. 렌더를 건너뛴다.", file=sys.stderr)
        return 1

    print("[3/5] 요약")
    summarized = summarize(picked, use_mock=use_mock)
    if not summarized:
        print("  ! 요약을 통과한 기사가 없다. 렌더를 건너뛴다.", file=sys.stderr)
        return 1

    print("[4/5] 같은 사건 합치기 · 최종 선정")
    final = finalize(summarized)
    print(f"  · 후보 {len(summarized)}건 → 최종 {len(final)}건")

    print("[5/5] 렌더")
    render(final, digest_date)
    # 실제로 내보낸 기사만 기록한다. 후보로만 뽑힌 기사는 내일 다시 후보가 된다.
    save_seen(seen, final, digest_date)
    return 0


if __name__ == "__main__":
    sys.exit(main(use_mock=True if "--mock" in sys.argv else None))
