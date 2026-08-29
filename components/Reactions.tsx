"use client";

import { useEffect, useState } from "react";

/** 세션 식별자. 같은 사람의 클릭을 묶기 위한 것으로, 개인정보는 담지 않는다. */
function sessionId(): string {
  try {
    let id = localStorage.getItem("f1-session");
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem("f1-session", id);
    }
    return id;
  } catch {
    return "no-storage";
  }
}

async function send(body: Record<string, unknown>): Promise<boolean> {
  try {
    const res = await fetch("/api/reaction", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ ...body, sessionId: sessionId() }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

type Vote = "up" | "down" | null;

/** 기사별 👍 / 👎. 매체별 반응 분포를 보기 위한 칸이다. */
export function ArticleVote({ articleId }: { articleId: string }) {
  const [vote, setVote] = useState<Vote>(null);

  function cast(value: "up" | "down") {
    if (vote) return;
    setVote(value);
    void send({ kind: "article", articleId, value });
  }

  return (
    <div className="reactions">
      <button className={`rbtn${vote === "up" ? " on" : ""}`} disabled={!!vote} onClick={() => cast("up")}>
        👍 도움이 됐다
      </button>
      <button className={`rbtn${vote === "down" ? " on" : ""}`} disabled={!!vote} onClick={() => cast("down")}>
        👎 아니다
      </button>
    </div>
  );
}

/**
 * Primary 지표: 방문 대비 '내일도 열어보겠다' 클릭 비율.
 *
 * 분모를 만들려면 누른 사람뿐 아니라 **본 사람**도 기록해야 한다.
 * 목록 화면이 뜨면 그날 1회 visit 행을 남긴다(같은 브라우저는 하루 한 번).
 */
export function RevisitAsk({ briefDate }: { briefDate: string }) {
  const [vote, setVote] = useState<Vote>(null);

  useEffect(() => {
    try {
      const visitKey = `f1-visit-${briefDate}`;
      if (!localStorage.getItem(visitKey)) {
        localStorage.setItem(visitKey, "1"); // 먼저 찍는다. 개발 모드의 이중 실행까지 막는다.
        void send({ kind: "visit" });
      }
      const saved = localStorage.getItem(`f1-revisit-${briefDate}`);
      if (saved === "up" || saved === "down") setVote(saved);
    } catch {
      // localStorage 를 못 쓰는 브라우저에서는 방문 기록을 남기지 않는다.
    }
  }, [briefDate]);

  function cast(value: "up" | "down") {
    if (vote) return;
    setVote(value);
    try {
      localStorage.setItem(`f1-revisit-${briefDate}`, value);
    } catch {
      // 저장이 안 돼도 클릭 자체는 기록한다. 집계는 session_id 기준으로 중복을 걷어낸다.
    }
    void send({ kind: "revisit", value });
  }

  return (
    <section className="ask">
      <h4>내일도 열어보시겠어요?</h4>
      <p>오늘 브리핑이 쓸모 있었는지 알려주세요.</p>
      <div className="reactions">
        <button className={`rbtn${vote === "up" ? " on" : ""}`} disabled={!!vote} onClick={() => cast("up")}>
          👍 내일도 열어보겠다
        </button>
        <button className={`rbtn${vote === "down" ? " on" : ""}`} disabled={!!vote} onClick={() => cast("down")}>
          👎 아니다
        </button>
      </div>
      {vote && <p className="done">기록했습니다. 고맙습니다.</p>}
    </section>
  );
}

/** 매체 수가 충분한지 검증하는 유일한 칸. */
export function MissingAsk() {
  const [note, setNote] = useState("");
  const [sent, setSent] = useState(false);

  async function submit() {
    const text = note.trim();
    if (!text || sent) return;
    setSent(true);
    await send({ kind: "missing", note: text });
  }

  return (
    <section className="ask">
      <h4>빠진 소식이 있나요?</h4>
      <p>오늘 여기서 못 본 F1 소식이 있다면 적어주세요.</p>
      {sent ? (
        <p className="done">보내주셔서 고맙습니다.</p>
      ) : (
        <>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="예: 페라리 팀 오더 관련 소식이 안 보였다"
            maxLength={500}
          />
          <button className="rbtn send" onClick={submit} disabled={!note.trim()}>
            보내기
          </button>
        </>
      )}
    </section>
  );
}
