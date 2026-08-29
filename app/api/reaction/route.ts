import { NextResponse } from "next/server";
import { saveReaction } from "@/lib/db";

export async function POST(request: Request) {
  let body: Record<string, unknown>;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "잘못된 요청" }, { status: 400 });
  }

  const kind = body.kind;
  const value = body.value;
  const sessionId = typeof body.sessionId === "string" ? body.sessionId.slice(0, 64) : "";

  const KINDS = ["article", "revisit", "missing", "visit"] as const;
  if (typeof kind !== "string" || !KINDS.includes(kind as (typeof KINDS)[number])) {
    return NextResponse.json({ error: "kind 가 올바르지 않다" }, { status: 400 });
  }
  // visit(방문 기록)과 missing(자유 응답)에는 up/down 이 없다.
  const needsValue = kind === "article" || kind === "revisit";
  if (needsValue && value !== "up" && value !== "down") {
    return NextResponse.json({ error: "value 가 올바르지 않다" }, { status: 400 });
  }
  if (!sessionId) {
    return NextResponse.json({ error: "sessionId 가 없다" }, { status: 400 });
  }

  try {
    await saveReaction({
      kind: kind as "article" | "revisit" | "missing" | "visit",
      articleId: kind === "article" ? String(body.articleId ?? "").slice(0, 64) || null : null,
      value: needsValue ? (value as "up" | "down") : null,
      note: kind === "missing" ? String(body.note ?? "").slice(0, 500) : null,
      sessionId,
    });
    return NextResponse.json({ ok: true });
  } catch (error) {
    console.error("[reaction]", error);
    return NextResponse.json({ error: "저장 실패" }, { status: 500 });
  }
}
