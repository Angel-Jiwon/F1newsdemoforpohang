import type { Metadata } from "next";
import Script from "next/script";
import "./globals.css";

export const metadata: Metadata = {
  title: "오늘의 F1 — 한국어 3줄 브리핑",
  description: "해외 F1 매체 3곳의 오늘 기사를 한국어 3줄 요약과 원문 링크로.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // NEXT_PUBLIC_GA_ID 를 넣으면 그때부터 GA4 가 붙는다. 없으면 아무것도 로드하지 않는다.
  const gaId = process.env.NEXT_PUBLIC_GA_ID;

  return (
    <html lang="ko">
      <body>
        <div className="shell">{children}</div>
        {gaId && (
          <>
            <Script src={`https://www.googletagmanager.com/gtag/js?id=${gaId}`} strategy="afterInteractive" />
            <Script id="ga" strategy="afterInteractive">
              {`window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}gtag('js',new Date());gtag('config','${gaId}');`}
            </Script>
          </>
        )}
      </body>
    </html>
  );
}
