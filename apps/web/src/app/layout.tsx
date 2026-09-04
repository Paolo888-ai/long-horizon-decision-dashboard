import type { Metadata } from "next";
import { GlossaryDrawer } from "@/components/glossary-drawer";
import "./globals.css";

export const metadata: Metadata = {
  title: "长期环境决策看板",
  description: "技术、信用、人口与历史周期分析",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}<GlossaryDrawer /></body>
    </html>
  );
}
