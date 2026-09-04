import type { ReactNode } from "react";
import { findGlossaryEntry } from "@/lib/glossary-data";

export function TermHelp({ term, children }: { term: string; children: ReactNode }) {
  const entry = findGlossaryEntry(term);
  return (
    <span className="term-help">
      <button type="button" aria-label={`解释：${term}`}>?</button>
      <span className="term-tooltip" role="tooltip">
        <span>{children}</span>
        {entry && <button className="term-more" type="button" onClick={() => window.dispatchEvent(new CustomEvent("glossary:open", { detail: entry.term }))}>在术语表中查看更多</button>}
      </span>
    </span>
  );
}

export function InterpretationPanel({ children }: { children: ReactNode }) {
  return (
    <aside className="interpretation-panel">
      <strong>这组数据怎么读</strong>
      <div>{children}</div>
    </aside>
  );
}
