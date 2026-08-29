/** Supabase 저장·조회 + 오늘치 브리핑 보장(ISR 진입점). */
import { createClient } from "@supabase/supabase-js";
import { collect } from "./feed";
import { summarize, analyze, type Analysis } from "./ai";

export type Article = {
  id: string;
  briefDate: string;
  source: string;
  sourcePriority: number;
  titleEn: string;
  titleKo: string;
  summaryKo: string[];
  storyKey: string;
  url: string;
  published: string;
  analysis: Analysis | null;
};

const db = createClient(process.env.SUPABASE_URL!, process.env.SUPABASE_ANON_KEY!, {
  auth: { persistSession: false },
});

// 진단용. 배포 환경이 어느 Supabase 프로젝트에 붙는지 에러 메시지로 확인한다.
// 원인이 잡히면 제거한다.
const TARGET = (() => {
  const url = process.env.SUPABASE_URL ?? "";
  const host = url.includes("supabase.co") ? url.replace(/^https?:\/\//, "").split(".")[0] : "(URL 없음)";
  return `${host} / key ${String(process.env.SUPABASE_ANON_KEY ?? "").length}자`;
})();

/** 화면에 올리는 기사 수. 후보는 이보다 넉넉히 모은다 —
 * 정보가 부족한 기사는 요약 단계에서 탈락하기 때문이다. */
const BRIEF_SIZE = 5;
const CANDIDATES = 12;

/** KST 기준 오늘 날짜. 브리핑의 단위는 한국 시간 하루다. */
export function today(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Seoul" }).format(new Date());
}

function toArticle(row: Record<string, any>): Article {
  return {
    id: row.id,
    briefDate: row.brief_date,
    source: row.source,
    sourcePriority: row.source_priority ?? 1,
    titleEn: row.title_en,
    titleKo: row.title_ko,
    summaryKo: row.summary_ko ?? [],
    storyKey: row.story_key ?? "",
    url: row.url,
    published: row.published,
    analysis: (row.analysis as Analysis) ?? null,
  };
}

async function readBriefing(date: string): Promise<Article[]> {
  const { data, error } = await db
    .from("articles")
    .select("*")
    .eq("brief_date", date)
    .order("published", { ascending: false });
  if (error) throw new Error(`articles 조회 실패: ${error.message} — 접속 대상: ${TARGET}`);
  return (data ?? []).map(toArticle);
}

// 같은 프로세스에서 동시에 두 번 수집하지 않도록 막는다.
let ingesting: Promise<Article[]> | null = null;

/**
 * 오늘치가 있으면 그대로, 없으면 수집·요약해서 채운 뒤 돌려준다.
 * 페이지가 ISR 로 재검증될 때 호출된다.
 */
export async function ensureToday(): Promise<Article[]> {
  const date = today();
  const existing = await readBriefing(date);
  if (existing.length > 0) return forList(existing);
  if (ingesting) return ingesting;

  ingesting = (async () => {
    const raw = await collect(CANDIDATES);
    const summaries = raw.length > 0 ? await summarize(raw) : [];
    const byId = new Map(summaries.map((s) => [s.id, s]));
    const rows = raw
      .filter((a) => byId.has(a.id))
      .map((a) => {
        const s = byId.get(a.id)!;
        return {
          id: a.id,
          brief_date: date,
          source: a.source,
          source_priority: a.sourcePriority,
          title_en: a.titleEn,
          title_ko: s.titleKo || a.titleEn,
          summary_ko: s.summaryKo,
          story_key: s.storyKey,
          url: a.url,
          published: a.published,
        };
      });
    if (rows.length > 0) {
      const { error } = await db.from("articles").upsert(rows, { onConflict: "id" });
      if (error) throw new Error(`articles 저장 실패: ${error.message}`);
    }
    // 수집에 실패했더라도 DB 를 다시 읽는다. 동시에 들어온 다른 방문자가
    // 이미 채워 뒀을 수 있고, 그 경우 빈 화면을 보여줄 이유가 없다.
    return forList(await readBriefing(date));
  })().finally(() => {
    ingesting = null;
  });

  return ingesting;
}

/**
 * 목록에 올릴 5건을 고른다.
 * 같은 사건(story_key)은 우선순위가 높은 매체 하나만 남긴다 —
 * 나머지는 상세 화면에서 "N 출처"로 함께 쓰인다.
 */
function forList(articles: Article[]): Article[] {
  const best = new Map<string, Article>();
  for (const a of articles) {
    const key = a.storyKey || a.id;
    const prev = best.get(key);
    if (!prev || a.sourcePriority > prev.sourcePriority) best.set(key, a);
  }
  const newest = [...best.values()].sort((a, b) => b.published.localeCompare(a.published));

  // 매체 3곳을 보여주는 것이 이 서비스의 전제다. 한 곳이 목록을 독식하지 않도록
  // 매체당 2건까지 먼저 채우고, 자리가 남으면 나머지로 마저 채운다.
  const picked: Article[] = [];
  const perSource = new Map<string, number>();
  for (const a of newest) {
    if (picked.length >= BRIEF_SIZE) break;
    const used = perSource.get(a.source) ?? 0;
    if (used >= 2) continue;
    perSource.set(a.source, used + 1);
    picked.push(a);
  }
  for (const a of newest) {
    if (picked.length >= BRIEF_SIZE) break;
    if (!picked.includes(a)) picked.push(a);
  }
  return picked;
}

export async function getArticle(id: string): Promise<Article | null> {
  const { data, error } = await db.from("articles").select("*").eq("id", id).maybeSingle();
  if (error) throw new Error(`기사 조회 실패: ${error.message}`);
  return data ? toArticle(data) : null;
}

/**
 * 상세 화면의 분석 리포트. 없으면 같은 사건(story_key)의 기사를 모두 출처로 묶어
 * 한 번 생성하고 저장한다. 다음 열람부터는 저장분을 그대로 쓴다.
 */
export async function ensureAnalysis(article: Article): Promise<{ analysis: Analysis | null; sources: Article[] }> {
  const sources = await relatedArticles(article);
  if (article.analysis) return { analysis: article.analysis, sources };

  const analysis = await analyze(
    { titleKo: article.titleKo, titleEn: article.titleEn },
    sources.map((s) => ({ source: s.source, title: s.titleEn, summary: s.summaryKo.join(" ") }))
  );
  const { error } = await db.from("articles").update({ analysis }).eq("id", article.id);
  if (error) console.error("[db] 분석 저장 실패:", error.message);
  return { analysis, sources };
}

/** 같은 사건을 다룬 기사들. story_key 가 비면 자기 자신뿐이다. */
async function relatedArticles(article: Article): Promise<Article[]> {
  if (!article.storyKey) return [article];
  const { data, error } = await db
    .from("articles")
    .select("*")
    .eq("brief_date", article.briefDate)
    .eq("story_key", article.storyKey);
  if (error || !data?.length) return [article];
  return data.map(toArticle);
}

export type ReactionInput = {
  kind: "article" | "revisit" | "missing" | "visit";
  articleId?: string | null;
  value?: "up" | "down" | null;
  note?: string | null;
  sessionId: string;
};

export async function saveReaction(input: ReactionInput): Promise<void> {
  const { error } = await db.from("reactions").insert({
    kind: input.kind,
    article_id: input.articleId ?? null,
    value: input.value ?? null,
    note: input.note ?? null,
    session_id: input.sessionId,
    brief_date: today(),
  });
  if (error) throw new Error(`반응 저장 실패: ${error.message}`);
}
