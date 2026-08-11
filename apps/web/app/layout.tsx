import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LiveOS",
  description: "LiveOS：理解你的生活，持续形成更适合你的居住决策。",
  icons: {
    icon: "/icon.svg",
    apple: "/icon.svg",
  },
  themeColor: "#050812",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
