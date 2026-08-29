import Link from "next/link";
import { notFound } from "next/navigation";
import { ensureAnalysis, getArticle, type Article } from "@/lib/db";
import { accentOf } from "@/lib/feed";
import { ArticleVote } from "@/components/Reactions";
import type { Analysis } from "@/lib/ai";

export const revalidate = 600;

export default async function ArticlePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  let article: Article | null = null;
  try {
    article = await getArticle(id);
  } catch (error) {
    console.error("[article]", error);
  }
  if (!article) notFound();

  let analysis: Analysis | null = null;
  let sources: Article[] = [article];
  let failure: string | null = null;
  try {
    const result = await ensureAnalysis(article);
    analysis = result.analysis;
    sources = result.sources.length > 0 ? result.sources : [article];
  } catch (error) {
    failure = error instanceof Error ? error.message : String(error);
    console.error("[analysis]", error);
  }

  const uniqueSources = [...new Set(sources.map((s) => s.source))];

  return (
    <>
      <div className="detailbar">
        <Link href="/" className="back" aria-label="목록으로">
          ←
        </Link>
        오늘의 F1
      </div>

      <article className="article">
        <div className="sourcepill">
          {uniqueSources.map((s) => (
            <span key={s} className="src">
              <span className="dot" style={{ background: accentOf(s) }} />
              {s}
            </span>
          ))}
          <span className="count">출처 {sources.length}건</span>
        </div>

        <h1>{article.titleKo}</h1>

        <ul className="summary3">
          {article.summaryKo.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>

        {analysis ? (
          <>
            <h3>개요</h3>
            <p>{analysis.overview}</p>
            {analysis.sections.map((section, i) => (
              <section key={i}>
                <h3>{section.title}</h3>
                <ul className="points">
                  {section.points.map((point, j) => (
                    <li key={j}>
                      <b>{point.lead}</b>
                      {point.lead && point.body ? ": " : ""}
                      {point.body}
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </>
        ) : (
          <p className="done">
            분석 리포트를 생성하지 못했습니다{failure ? ` (${failure})` : ""}. 위 3줄 요약과 아래 원문을 확인해 주세요.
          </p>
        )}

        <h3>원문</h3>
        {sources.map((s) => (
          <a key={s.id} className="origin" href={s.url} target="_blank" rel="noopener noreferrer">
            {s.titleEn}
            <span>
              {s.source} · 원문 보기 ↗
            </span>
          </a>
        ))}

        <h3>이 기사, 도움이 됐나요?</h3>
        <ArticleVote articleId={article.id} />
      </article>
    </>
  );
}
