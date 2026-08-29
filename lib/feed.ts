/**
 * RSS 3곳 수집 → 정규화 → F1 필터 → 중복 제거.
 *
 * 소스 표는 여기가 단일 진실 공급원이다. 세 피드 모두 200 응답과
 * <item> 구조를 확인했다(1차 MVP 검증 결과를 그대로 승계).
 */
import { createHash } from "node:crypto";
import { XMLParser } from "fast-xml-parser";

export type Source = {
  name: string;
  /** 중복 기사 중 남길 매체 결정. 높을수록 우선. */
  priority: number;
  /** false 인 소스는 F1 필터를 반드시 통과시켜야 한다. */
  f1Only: boolean;
  rss: string;
  /** 목록 화면 왼쪽 악센트 바 색. */
  accent: string;
};

export const SOURCES: Source[] = [
  { name: "BBC Sport", priority: 3, f1Only: true, rss: "https://feeds.bbci.co.uk/sport/formula1/rss.xml", accent: "#e4572e" },
  { name: "Autosport", priority: 2, f1Only: true, rss: "https://www.autosport.com/rss/f1/news/", accent: "#f2a03d" },
  { name: "The Race", priority: 1, f1Only: false, rss: "https://www.the-race.com/rss/", accent: "#2f6fed" },
];

export type RawArticle = {
  id: string;
  source: string;
  sourcePriority: number;
  titleEn: string;
  summaryEn: string;
  url: string;
  published: string; // ISO
};

/** 추적 파라미터. 제거해야 id(url 해시)가 안정적이다. */
const TRACKING = /^(utm_|at_)/;

function cleanUrl(raw: string): string {
  try {
    const u = new URL(raw.trim());
    for (const key of [...u.searchParams.keys()]) {
      if (TRACKING.test(key)) u.searchParams.delete(key);
    }
    u.hash = "";
    return u.toString();
  } catch {
    return raw.trim();
  }
}

/** RSS description 에 섞여 오는 태그·엔티티·"Keep reading" 을 걷어낸다. */
function cleanText(raw: unknown): string {
  const text = typeof raw === "string" ? raw : "";
  return text
    .replace(/<[^>]*>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;|&apos;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/\bKeep reading\b/gi, "")
    .replace(/\s+/g, " ")
    .trim();
}

const F1_PATHS = ["/f1/", "/formula-1/", "/formula1/"];
const OTHER_SERIES = ["formula e", "motogp", "indycar", "wec", "btcc", "nascar", "wrc", "le mans", "f2 ", "f3 "];

/** f1Only: false 인 소스 판정. 판정 불가는 제외한다 — 오탐이 누락보다 나쁘다. */
function isF1(url: string, categories: string[], title: string, summary: string): boolean {
  const lowerUrl = url.toLowerCase();
  if (F1_PATHS.some((p) => lowerUrl.includes(p))) return true;
  if (categories.some((c) => /formula\s*1|^f1$/i.test(c.trim()))) return true;
  const blob = `${title} ${summary}`.toLowerCase();
  if (OTHER_SERIES.some((k) => blob.includes(k))) return false;
  return false;
}

/** F1 항목이어도 기사가 아니면 3문장 요약이 성립하지 않는다. */
function isArticle(title: string, url: string): boolean {
  const t = title.toLowerCase().trim();
  if (/\bquiz\b|\bpodcast\b|q&a/.test(t)) return false;
  if (t === "f1: chequered flag") return false;
  if (url.toLowerCase().includes("/av/")) return false;
  return true;
}

const parser = new XMLParser({ ignoreAttributes: false, attributeNamePrefix: "@_" });

function asArray<T>(value: T | T[] | undefined): T[] {
  if (value === undefined || value === null) return [];
  return Array.isArray(value) ? value : [value];
}

async function fetchSource(source: Source): Promise<RawArticle[]> {
  const res = await fetch(source.rss, {
    headers: { "user-agent": "f1-briefing/2.0 (+https://github.com)" },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`${source.name} RSS ${res.status}`);
  const xml = parser.parse(await res.text());
  const items = asArray<Record<string, unknown>>(xml?.rss?.channel?.item);

  const articles: RawArticle[] = [];
  for (const item of items) {
    // content:encoded 에 전문이 실려 오는 소스가 있다. 읽지 않는다 — description 만 쓴다.
    const url = cleanUrl(String(item.link ?? ""));
    const titleEn = cleanText(item.title);
    const summaryEn = cleanText(item.description);
    if (!url || !titleEn) continue;

    const categories = asArray<unknown>(item.category as never).map((c) =>
      typeof c === "string" ? c : String((c as Record<string, unknown>)?.["#text"] ?? "")
    );
    if (!source.f1Only && !isF1(url, categories, titleEn, summaryEn)) continue;
    if (!isArticle(titleEn, url)) continue;

    const pub = item.pubDate ? new Date(String(item.pubDate)) : new Date();
    articles.push({
      id: createHash("sha1").update(url).digest("hex").slice(0, 12),
      source: source.name,
      sourcePriority: source.priority,
      titleEn,
      summaryEn,
      url,
      published: (isNaN(pub.getTime()) ? new Date() : pub).toISOString(),
    });
  }
  return articles;
}

/**
 * 세 소스를 모아 최신순 상위 `limit` 건을 돌려준다.
 * 한 소스가 죽어도 나머지로 브리핑은 나가야 한다.
 */
export async function collect(limit = 12): Promise<RawArticle[]> {
  const results = await Promise.allSettled(SOURCES.map(fetchSource));
  const all: RawArticle[] = [];
  for (const [i, r] of results.entries()) {
    if (r.status === "fulfilled") all.push(...r.value);
    else console.error(`[feed] ${SOURCES[i].name} 실패:`, r.reason);
  }

  // 같은 URL 은 우선순위 높은 매체만 남긴다.
  const byId = new Map<string, RawArticle>();
  for (const a of all) {
    const prev = byId.get(a.id);
    if (!prev || a.sourcePriority > prev.sourcePriority) byId.set(a.id, a);
  }

  return [...byId.values()]
    .sort((a, b) => b.published.localeCompare(a.published))
    .slice(0, limit);
}

export function accentOf(sourceName: string): string {
  return SOURCES.find((s) => s.name === sourceName)?.accent ?? "#8a8f98";
}
