import Link from "next/link";

import { SimilarityEvidence } from "@/components/similarity-evidence";
import { CrossCountryEvidence } from "@/components/cross-country-evidence";

export default function SimilarityResearchPage() {
  return (
    <main className="research-shell">
      <header className="research-nav">
        <Link href="/">← 返回看板</Link>
        <span>长期环境决策看板 / 研究实验室</span>
      </header>
      <SimilarityEvidence />
      <CrossCountryEvidence />
      <footer>回测页面不构成投资、职业、迁移或家庭决策建议。</footer>
    </main>
  );
}
