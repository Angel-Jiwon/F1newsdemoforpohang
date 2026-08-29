"use client";

import Script from "next/script";
import { useEffect, useState } from "react";

/**
 * GA4 는 동의를 받은 뒤에만 로드한다.
 *
 * 스크립트를 먼저 넣고 끄는 방식이 아니라, 동의 전에는 아예 요청하지 않는다.
 * NEXT_PUBLIC_GA_ID 가 없으면 이 컴포넌트 자체가 렌더되지 않는다(레이아웃에서 분기).
 */
const KEY = "f1-consent";

type Choice = "granted" | "denied";

export function Analytics({ gaId }: { gaId: string }) {
  // undefined = 아직 localStorage 를 읽기 전. 서버·클라이언트 첫 렌더를 맞추기 위해 아무것도 그리지 않는다.
  const [choice, setChoice] = useState<Choice | null | undefined>(undefined);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(KEY);
      setChoice(saved === "granted" || saved === "denied" ? saved : null);
    } catch {
      setChoice("denied"); // 저장을 못 하면 매번 다시 물어야 한다. 그럴 바엔 켜지 않는다.
    }
  }, []);

  function decide(value: Choice) {
    try {
      localStorage.setItem(KEY, value);
    } catch {
      /* 저장이 안 되면 이번 방문에만 적용된다 */
    }
    setChoice(value);
  }

  if (choice === undefined) return null;

  if (choice === "granted") {
    return (
      <>
        <Script src={`https://www.googletagmanager.com/gtag/js?id=${gaId}`} strategy="afterInteractive" />
        <Script id="ga" strategy="afterInteractive">
          {`window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}gtag('js',new Date());gtag('config','${gaId}');`}
        </Script>
      </>
    );
  }

  if (choice === "denied") return null;

  return (
    <div className="consent" role="dialog" aria-label="쿠키 사용 동의">
      <p>
        방문 통계를 보기 위해 Google Analytics 쿠키를 사용합니다. 거부해도 브리핑을 보는 데는 아무 지장이 없습니다.
      </p>
      <div className="reactions">
        <button className="rbtn" onClick={() => decide("denied")}>
          거부
        </button>
        <button className="rbtn on" onClick={() => decide("granted")}>
          동의
        </button>
      </div>
    </div>
  );
}
