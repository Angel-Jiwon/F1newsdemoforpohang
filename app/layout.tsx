import type { Metadata } from "next";
import { Analytics } from "@/components/Analytics";
import "./globals.css";

export const metadata: Metadata = {
  title: "오늘의 F1 — 한국어 3줄 브리핑",
  description: "해외 F1 매체 3곳의 오늘 기사를 한국어 3줄 요약과 원문 링크로.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // NEXT_PUBLIC_GA_ID 를 넣으면 동의 배너가 뜨고, 동의한 방문자에게만 GA4 가 로드된다.
  const gaId = process.env.NEXT_PUBLIC_GA_ID;

  return (
    <html lang="ko">
      <body>
        <div className="shell">{children}</div>
        {gaId && <Analytics gaId={gaId} />}
      </body>
    </html>
  );
}
