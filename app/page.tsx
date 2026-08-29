import Link from "next/link";
import { ensureToday, today, type Article } from "@/lib/db";
import { SOURCES, accentOf } from "@/lib/feed";
import { MissingAsk, RevisitAsk } from "@/components/Reactions";

// 방문 시 자동 갱신. 오늘치가 없으면 그때 수집·요약한다.
export const revalidate = 600;

function ago(iso: string): string {
  const minutes = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (minutes < 60) return `${minutes}분 전`;
  if (minutes < 60 * 24) return `${Math.floor(minutes / 60)}시간 전`;
  return `${Math.floor(minutes / 1440)}일 전`;
}

function koDate(date: string): string {
  const [y, m, d] = date.split("-");
  return `${y}년 ${Number(m)}월 ${Number(d)}일`;
}

function Badge({ source }: { source: string }) {
  return (
    <span className="badge" style={{ background: accentOf(source) }}>
      {source.slice(0, 1)}
    </span>
  );
}

export default async function Home() {
  let articles: Article[] = [];
  let failure: string | null = null;
  try {
    articles = await ensureToday();
  } catch (error) {
    failure = error instanceof Error ? error.message : String(error);
    console.error("[page]", error);
  }

  return (
    <>
      <header className="topbar">
        <h1>오늘의 F1</h1>
        <span className="spacer" />
        <span className="date">{koDate(today())}</span>
      </header>

      <div className="chips">
        <span className="chip active">🏁 오늘의 브리핑</span>
        {SOURCES.map((s) => (
          <span key={s.name} className="chip">
            <span className="dot" style={{ background: s.accent }} />
            {s.name}
          </span>
        ))}
      </div>

      {articles.length === 0 ? (
        <p className="empty">
          {failure
            ? `브리핑을 불러오지 못했습니다.\n${failure}`
            : "오늘 아직 올라온 기사가 없습니다.\n잠시 뒤 다시 열어주세요."}
        </p>
      ) : (
        <div className="list">
          {articles.map((a) => (
            <Link key={a.id} href={`/article/${a.id}`} className="item" style={{ borderLeftColor: accentOf(a.source) }}>
              <h2>{a.titleKo}</h2>
              <p className="lede">{a.summaryKo[0]}</p>
              <div className="meta">
                <Badge source={a.source} />
                {a.source} · {ago(a.published)}
              </div>
            </Link>
          ))}
        </div>
      )}

      {articles.length > 0 && (
        <>
          <RevisitAsk />
          <MissingAsk />
        </>
      )}

      <p className="footer">
        해외 F1 매체 {SOURCES.length}곳의 오늘 기사를 한국어 3줄로 요약합니다. 요약은 각 매체의 RSS 요약문만 근거로
        생성되며, 정확한 내용은 원문에서 확인해 주세요.
      </p>
    </>
  );
}
