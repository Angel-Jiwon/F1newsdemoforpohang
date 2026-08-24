"""docs/index.html 생성.

프레임워크·빌드 도구 없이 정적 HTML 한 파일을 문자열로 만든다.
"""
from __future__ import annotations

import html
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
ARCHIVE = DOCS / "archive"

KST = timezone(timedelta(hours=9))
# 공개 페이지라 개인 이메일 대신 저장소 이슈 창구를 쓴다.
CONTACT_URL = "https://github.com/Angel-Jiwon/F1newsdemoforpohang/issues"
CONTACT_LABEL = "GitHub Issues"

# 👍/👎 저장소. 값은 환경변수로만 받는다 (코딩 규칙: 키를 커밋하지 않는다).
#   SUPABASE_URL       = https://<project-ref>.supabase.co
#   SUPABASE_ANON_KEY  = anon public 키 (service_role 아님)
# 비어 있으면 localStorage 에만 기록하고 전송하지 않는다.
#
# anon 키는 정적 HTML 에 그대로 박혀 공개된다. 이는 설계상 의도된 것이며,
# feedback 테이블의 RLS 가 INSERT 만 허용하기 때문에 성립한다.

DISCLAIMER = f"""<h2>안내</h2>
<ul>
  <li>본 서비스는 Formula 1, FIA, Formula One World Championship Limited 및 각 매체와 아무런 제휴 관계가 없는 비공식·개인 프로젝트입니다.</li>
  <li>F1&reg;, FORMULA 1&reg; 등은 Formula One Licensing B.V.의 등록 상표입니다.</li>
  <li>모든 기사의 저작권은 각 매체에 있습니다. 본 서비스는 원문을 제공하지 않으며, AI가 생성한 짧은 한국어 요약과 원문 링크만 제공합니다.</li>
  <li>요약은 AI가 자동 생성한 것으로 오역&middot;오류가 있을 수 있습니다. <strong>정확한 내용은 반드시 원문을 확인해 주세요.</strong></li>
  <li>게재 중단을 원하는 매체는 <a href="{CONTACT_URL}" target="_blank" rel="noopener noreferrer">{CONTACT_LABEL}</a>로 알려주시면 즉시 조치하겠습니다.</li>
</ul>"""

STYLE = """
:root {
  --bg: #0d0d12;
  --card: #17171f;
  --card-2: #1e1e28;
  --border: #262632;
  --text: #f4f4f7;
  --muted: #8b8b9c;
  --dim: #5f5f70;
  --accent: #7b5cfa;
  --accent-soft: rgba(123, 92, 250, 0.16);
  --bbc: #ff5a5a;
  --autosport: #ffb020;
  --therace: #4ecdc4;
}
*, *::before, *::after { box-sizing: border-box; }
body {
  margin: 0; padding: 0 20px 56px;
  font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo",
               "Pretendard", "Malgun Gothic", "Noto Sans KR", sans-serif;
  line-height: 1.65; color: var(--text); background: var(--bg);
  -webkit-text-size-adjust: 100%; -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 620px; margin: 0 auto; }

header { padding: 44px 0 4px; }
h1 { margin: 0; font-size: 30px; font-weight: 800; letter-spacing: -0.03em; }
.date { margin: 8px 0 0; color: var(--muted); font-size: 14px; }
.sources { display: flex; flex-wrap: wrap; gap: 8px; margin: 18px 0 0; }
.chip {
  display: inline-flex; align-items: center; gap: 7px;
  font-size: 13px; font-weight: 600; padding: 7px 14px; border-radius: 999px;
  background: var(--card); border: 1px solid var(--border); color: #c9c9d6;
}
.chip i { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.chip[data-s="BBC Sport"] i { background: var(--bbc); }
.chip[data-s="Autosport"] i { background: var(--autosport); }
.chip[data-s="The Race"] i { background: var(--therace); }

.section {
  display: flex; align-items: center; gap: 8px;
  margin: 32px 0 4px; font-size: 15px; font-weight: 700; letter-spacing: -0.01em;
}
.section .mark {
  display: grid; place-items: center; width: 26px; height: 26px;
  border-radius: 8px; background: var(--accent-soft); color: var(--accent); font-size: 14px;
}

.shortfall {
  margin: 18px 0 0; padding: 13px 15px; border-radius: 12px; font-size: 14px;
  background: rgba(255, 176, 32, 0.09); border: 1px solid rgba(255, 176, 32, 0.28);
  color: #f0bc63;
}

.card {
  display: grid; grid-template-columns: 34px 1fr; gap: 14px;
  background: var(--card); border: 1px solid var(--border); border-radius: 18px;
  padding: 20px 18px; margin: 14px 0;
}
.rank {
  font-size: 19px; font-weight: 800; color: var(--dim);
  letter-spacing: -0.02em; line-height: 1.5; font-variant-numeric: tabular-nums;
}
.meta { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; font-size: 12.5px; }
.source { font-weight: 700; letter-spacing: 0.01em; }
.source[data-s="BBC Sport"] { color: var(--bbc); }
.source[data-s="Autosport"] { color: var(--autosport); }
.source[data-s="The Race"] { color: var(--therace); }
.dot { width: 3px; height: 3px; border-radius: 50%; background: var(--dim); }
.time { color: var(--muted); }

.card h2 {
  margin: 10px 0 6px; font-size: 19px; font-weight: 700;
  line-height: 1.4; letter-spacing: -0.02em;
}
.title-en { margin: 0 0 14px; font-size: 13px; color: var(--dim); line-height: 1.5; }

.summary { margin: 0; padding: 0; list-style: none; }
.summary li {
  position: relative; padding-left: 15px; margin-bottom: 8px;
  font-size: 14.5px; color: #d3d3dd;
}
.summary li:last-child { margin-bottom: 0; }
.summary li::before {
  content: ""; position: absolute; left: 0; top: 9px;
  width: 5px; height: 5px; border-radius: 50%; background: var(--accent);
}

.actions {
  display: flex; align-items: center; gap: 8px;
  margin-top: 18px; padding-top: 15px; border-top: 1px solid var(--border);
}
.origin {
  font-size: 14px; font-weight: 600; color: var(--accent); text-decoration: none;
  margin-right: auto;
}
.origin:hover { text-decoration: underline; }
.vote {
  font: inherit; font-size: 15px; line-height: 1; cursor: pointer;
  padding: 8px 13px; border: 1px solid var(--border); border-radius: 999px;
  background: var(--card-2); color: var(--text);
  transition: background 0.15s, border-color 0.15s;
}
.vote:hover { background: #262633; }
.vote[aria-pressed="true"] { background: var(--accent-soft); border-color: var(--accent); }
.vote:disabled { cursor: default; opacity: 0.35; }
.vote[aria-pressed="true"]:disabled { opacity: 1; }

footer {
  margin-top: 40px; padding: 22px 18px; border-radius: 18px;
  background: var(--card); border: 1px solid var(--border);
  font-size: 12.5px; color: var(--muted); line-height: 1.7;
}
footer h2 { font-size: 13px; margin: 0 0 12px; color: var(--text); font-weight: 700; }
footer ul { margin: 0; padding-left: 16px; }
footer li { margin-bottom: 8px; }
footer li:last-child { margin-bottom: 0; }
footer a { color: var(--accent); }
footer strong { color: #d3d3dd; }
"""

SCRIPT_TEMPLATE = """
var SUPABASE_URL = %(supabase_url)s;
var SUPABASE_ANON_KEY = %(supabase_key)s;
var DIGEST_DATE = %(digest_date)s;
var STORAGE_KEY = "f1brief.votes";

function readVotes() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {}; }
  catch (e) { return {}; }
}

function writeVotes(votes) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(votes)); }
  catch (e) { /* 사생활 보호 모드 등. 기록만 못 할 뿐 동작은 계속한다. */ }
}

// 중복 투표 방지는 localStorage 로만 한다. 완벽하지 않아도 MVP 엔 충분하다.
function lock(card, vote) {
  card.querySelectorAll(".vote").forEach(function (button) {
    button.disabled = true;
    button.setAttribute("aria-pressed", String(Number(button.dataset.vote) === vote));
  });
}

function send(articleId, vote) {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) return;  // 미연결 상태에서는 전송하지 않는다
  fetch(SUPABASE_URL + "/rest/v1/feedback", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "apikey": SUPABASE_ANON_KEY,
      "Authorization": "Bearer " + SUPABASE_ANON_KEY,
      "Prefer": "return=minimal"
    },
    body: JSON.stringify({
      digest_date: DIGEST_DATE,
      article_id: articleId,
      vote: vote
    })
  }).catch(function () { /* 실패해도 화면은 그대로 둔다 */ });
}

document.addEventListener("DOMContentLoaded", function () {
  var votes = readVotes();

  document.querySelectorAll(".card").forEach(function (card) {
    var articleId = card.dataset.articleId;
    if (articleId in votes) lock(card, votes[articleId]);

    card.querySelectorAll(".vote").forEach(function (button) {
      button.addEventListener("click", function () {
        if (articleId in votes) return;
        var vote = Number(button.dataset.vote);
        votes[articleId] = vote;
        writeVotes(votes);
        lock(card, vote);
        send(articleId, vote);
      });
    });
  });
});
"""


def _kst_time(published: str) -> str:
    dt = datetime.strptime(published, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return dt.astimezone(KST).strftime("%m월 %d일 %H:%M")


def _card(article: dict, rank: int) -> str:
    e = html.escape
    sentences = "\n".join(f"            <li>{e(s)}</li>" for s in article["summary_ko"])
    return f"""      <article class="card" data-article-id="{e(article['id'])}">
        <div class="rank">{rank:02d}</div>
        <div>
          <div class="meta">
            <span class="source" data-s="{e(article['source'])}">{e(article['source'])}</span>
            <span class="dot"></span>
            <span class="time">{e(_kst_time(article['published']))} KST</span>
          </div>
          <h2>{e(article['title_ko'])}</h2>
          <p class="title-en">{e(article['title_en'])}</p>
          <ul class="summary">
{sentences}
          </ul>
          <div class="actions">
            <a class="origin" href="{e(article['url'])}" target="_blank" rel="noopener noreferrer">원문 보기 &rarr;</a>
            <button class="vote" type="button" data-vote="1" aria-pressed="false" aria-label="도움이 됐어요">👍</button>
            <button class="vote" type="button" data-vote="-1" aria-pressed="false" aria-label="도움이 안 됐어요">👎</button>
          </div>
        </div>
      </article>"""


def build_html(articles: list[dict], digest_date: str) -> str:
    """요약 3문장 계약을 여기서 마지막으로 강제한다."""
    for article in articles:
        if len(article["summary_ko"]) != 3:
            raise ValueError(
                f"summary_ko 가 3문장이 아니다 ({len(article['summary_ko'])}문장): "
                f"{article['title_en']}"
            )

    cards = "\n".join(_card(a, i) for i, a in enumerate(articles, start=1))
    shortfall = ""
    if len(articles) < 5:
        shortfall = (
            f'      <p class="shortfall">오늘은 조건을 만족하는 기사가 {len(articles)}건입니다. '
            "빈칸을 채우기 위해 관련 없는 기사를 넣지 않습니다.</p>"
        )

    # 필터가 아니라 출처 표시다. 세 곳 모두 동등하게 보여준다.
    chips = "\n".join(
        f'        <span class="chip" data-s="{name}"><i></i>{html.escape(name)}</span>'
        for name in ("BBC Sport", "Autosport", "The Race")
    )

    script = SCRIPT_TEMPLATE % {
        "supabase_url": json.dumps(os.environ.get("SUPABASE_URL", "")),
        "supabase_key": json.dumps(os.environ.get("SUPABASE_ANON_KEY", "")),
        "digest_date": json.dumps(digest_date),
    }

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<meta name="theme-color" content="#0d0d12">
<title>오늘의 F1 브리핑 · {digest_date}</title>
<meta name="description" content="해외 F1 매체의 주요 기사를 한국어 3줄 요약과 원문 링크로 전합니다.">
<style>{STYLE}</style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>오늘의 F1 브리핑</h1>
      <p class="date">{digest_date}</p>
      <div class="sources">
{chips}
      </div>
    </header>
    <main>
      <p class="section"><span class="mark">🔥</span>오늘의 기사 {len(articles)}건</p>
{shortfall}
{cards}
    </main>
    <footer>
{DISCLAIMER}
    </footer>
  </div>
<script>{script}</script>
</body>
</html>
"""


def render(articles: list[dict], digest_date: str | None = None) -> Path:
    """docs/index.html 과 docs/archive/YYYY-MM-DD.html 을 함께 쓴다."""
    digest_date = digest_date or datetime.now(KST).strftime("%Y-%m-%d")
    page = build_html(articles, digest_date)

    ARCHIVE.mkdir(parents=True, exist_ok=True)
    index = DOCS / "index.html"
    index.write_text(page, encoding="utf-8")
    (ARCHIVE / f"{digest_date}.html").write_text(page, encoding="utf-8")
    print(f"  · {index.relative_to(ROOT)} ({len(articles)}건)")
    print(f"  · docs/archive/{digest_date}.html")
    return index
