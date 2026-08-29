import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "오늘의 F1 — 한국어 3줄 브리핑",
  description: "해외 F1 매체 3곳의 오늘 기사를 한국어 3줄 요약과 원문 링크로.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <div className="shell">{children}</div>
      </body>
    </html>
  );
}
