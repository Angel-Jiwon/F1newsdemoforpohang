/**
 * Gemini REST 호출. SDK 없이 fetch 로 직접 친다.
 *
 * - 목록용 3문장 요약: 5건을 한 번에 묶어 호출 1회.
 * - 상세용 분석 리포트: 기사 1건 열람 시 1회, 결과는 DB 에 저장해 재사용.
 *
 * ⚠️ 엔드포인트/모델은 1차 MVP 에서 실측 검증한 조합이다.
 *    gemini-2.5-flash 는 신규 사용자에게 404 가 돌아온다.
 */
import type { RawArticle } from "./feed";

const ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions";
const MODEL = process.env.GEMINI_MODEL || "gemini-3.6-flash";
const RETRY_STATUSES = new Set([429, 500, 502, 503, 504]);
const BACKOFF_MS = [5000, 20000, 60000];

export type Summary = {
  id: string;
  titleKo: string;
  summaryKo: string[];
  storyKey: string;
  insufficient?: boolean;
};

export type Analysis = {
  overview: string;
  sections: { title: string; points: { lead: string; body: string }[] }[];
};

const SYSTEM_SUMMARY = `당신은 해외 F1 뉴스를 한국 팬에게 전달하는 에디터입니다.

원칙:
- 입력으로 주어진 제목과 RSS 요약문에 **명시된 내용만** 사용합니다. 배경지식으로 사실을 보충하지 않습니다.
- 원문 표현을 그대로 옮기지 않고 자신의 문장으로 재구성합니다.
- 요약은 **정확히 3문장**입니다. 1문장: 무슨 일이 있었는가 / 2문장: 누가·어디서·언제 등 구체 정보 / 3문장: 왜 중요한가.
- 추측과 논평을 넣지 않습니다.
- 원문 요약문이 한두 줄로 짧은 경우가 많습니다. 그때도 3문장을 만듭니다. 3번째 문장은 다음 중 하나로 씁니다.
  (a) 원문에 근거가 있는 의미·배경·다음 일정, (b) 원문이 밝히지 않은 부분을 그대로 명시(예: 구체적인 조사 일정은 공개되지 않았다).
  **없는 사실·수치·인용을 지어내는 것은 어떤 경우에도 금지합니다.**
  ❌ "이 소식은 BBC Sport가 전했다" 처럼 매체 이름만 붙여 분량을 채우는 문장은 쓰지 마십시오. 독자에게 새 정보가 없습니다.
- 기사가 아니어서 요약 자체가 성립하지 않을 때만(질문 모집, 팟캐스트 안내 등) insufficient: true 로 표시합니다.

같은 사건 묶기(story_key): 각 기사가 다루는 사건에 <대회>-<사건> 형식의 영문 소문자 하이픈 식별자를 붙입니다.
매체가 달라도 같은 사건이면 반드시 같은 값을 씁니다. 같은 대회라도 결승 결과·예선 결과·사고·인터뷰는 서로 다른 사건입니다.

표기: 드라이버·팀명은 한국 팬 통용 표기(막스 페르스타펀, 랜도 노리스, 페르난도 알론소, 샤를 르클레르, 페라리, 레드불, 메르세데스, 맥라렌, 애스턴 마틴, 알핀).
영문 약어는 괄호 없이 그대로 씁니다(FIA, GP, ADUO). 한글 음차(피아)로 적지 않습니다.
경기 용어는 한국어 정착 표기(폴 포지션, 퀄리파잉, 피트스톱, 세이프티카, 그리드 강등). 그랑프리는 "네덜란드 GP" 형식.
문체: 평서형 '~다' 신문 기사체. 이모지·느낌표 없음. 한 문장 60자 내외.

출력은 JSON 배열만. 코드블록이나 설명 문장을 붙이지 마십시오.
[{"id":"입력과 동일한 id","title_ko":"한국어 제목(40자 이내)","summary_ko":["문장1","문장2","문장3"],"story_key":"dutch-gp-race-result","insufficient":false}]`;

const SYSTEM_ANALYSIS = `당신은 해외 F1 뉴스를 한국 팬에게 정리해 주는 애널리스트입니다.

가장 중요한 원칙: **주어진 출처 기사들에 명시된 내용만** 씁니다. 배경지식으로 사실·수치·순위를 보충하지 않습니다.
근거가 없는 전망, 추측, 평가는 쓰지 않습니다. 출처가 적으면 리포트도 짧아야 합니다. 분량을 채우려 지어내지 마십시오.

구성:
- overview: 이 사건이 무엇인지 3~4문장. 출처에 있는 사실만.
- sections: 2~3개. 각 섹션은 title(예: "무슨 일이 있었나", "주요 사실", "다음 관전 포인트")과 points 2~4개.
  각 point 는 lead(굵게 표시될 짧은 핵심구, 20자 내외)와 body(1~2문장 설명)로 나눕니다.
  body 안에서 근거가 된 매체를 "BBC Sport에 따르면"처럼 밝힐 수 있습니다.

표기·문체는 한국 F1 팬 통용 표기와 평서형 '~다' 기사체를 씁니다. 이모지·느낌표를 쓰지 않습니다.

출력은 JSON 객체만. 코드블록이나 설명 문장을 붙이지 마십시오.
{"overview":"...","sections":[{"title":"...","points":[{"lead":"...","body":"..."}]}]}`;

function extractText(res: unknown): string {
  const r = res as Record<string, any>;
  if (typeof r?.output_text === "string" && r.output_text.trim()) return r.output_text;
  const chunks: string[] = [];
  for (const step of r?.steps ?? []) {
    if (step?.type !== "model_output") continue; // thought(내부 추론)는 버린다
    for (const part of step?.content ?? []) {
      if (part?.type === "text" && typeof part.text === "string") chunks.push(part.text);
    }
  }
  if (chunks.join("").trim()) return chunks.join("");
  throw new Error(`응답에서 생성 텍스트를 찾지 못했다: ${JSON.stringify(res).slice(0, 300)}`);
}

function parseJson<T>(text: string): T {
  const cleaned = text.trim().replace(/^```(?:json)?\s*/m, "").replace(/\s*```$/m, "");
  return JSON.parse(cleaned) as T;
}

async function call(system: string, input: string): Promise<string> {
  const key = process.env.GEMINI_API_KEY;
  if (!key) throw new Error("GEMINI_API_KEY 없음");

  for (let attempt = 0; attempt < 4; attempt++) {
    const res = await fetch(ENDPOINT, {
      method: "POST",
      headers: { "content-type": "application/json", "x-goog-api-key": key },
      body: JSON.stringify({ model: MODEL, system_instruction: system, input }),
      cache: "no-store",
    });
    if (res.ok) return extractText(await res.json());

    const detail = (await res.text()).slice(0, 300);
    if (!RETRY_STATUSES.has(res.status) || attempt === 3) {
      throw new Error(`Gemini API ${res.status}: ${detail}`);
    }
    console.error(`[ai] ${res.status} — ${BACKOFF_MS[attempt] / 1000}초 후 재시도`);
    await new Promise((r) => setTimeout(r, BACKOFF_MS[attempt]));
  }
  throw new Error("Gemini API 재시도 한도 초과");
}

/** 5건 묶음 → 3문장 요약. 3문장이 아니거나 정보가 부족한 건은 빠진 채로 돌아온다. */
export async function summarize(articles: RawArticle[]): Promise<Summary[]> {
  if (articles.length === 0) return [];

  const payload = JSON.stringify(
    articles.map((a) => ({ id: a.id, source: a.source, title: a.titleEn, rss_summary: a.summaryEn })),
    null,
    2
  );
  const text = await call(SYSTEM_SUMMARY, `다음 ${articles.length}건의 F1 기사를 처리하십시오.\n\n${payload}`);
  const raw = parseJson<Record<string, any>[]>(text);

  return raw
    .filter((r) => !r.insufficient && Array.isArray(r.summary_ko) && r.summary_ko.length === 3)
    .map((r) => ({
      id: String(r.id),
      titleKo: String(r.title_ko ?? "").slice(0, 40),
      summaryKo: r.summary_ko as string[],
      storyKey: String(r.story_key ?? ""),
    }));
}

/** 같은 사건을 다룬 기사 전부를 출처로 묶어 분석 리포트 1건을 만든다. */
export async function analyze(
  target: { titleKo: string; titleEn: string },
  sources: { source: string; title: string; summary: string }[]
): Promise<Analysis> {
  const payload = JSON.stringify({ 주제: target.titleKo || target.titleEn, 출처: sources }, null, 2);
  const text = await call(
    SYSTEM_ANALYSIS,
    `다음 출처 기사들을 근거로 "${target.titleKo || target.titleEn}"에 대한 분석 리포트를 작성하십시오.\n\n${payload}`
  );
  const raw = parseJson<Record<string, any>>(text);
  return {
    overview: String(raw.overview ?? ""),
    sections: (raw.sections ?? []).map((s: Record<string, any>) => ({
      title: String(s.title ?? ""),
      points: (s.points ?? []).map((p: Record<string, any>) => ({
        lead: String(p.lead ?? ""),
        body: String(p.body ?? ""),
      })),
    })),
  };
}
