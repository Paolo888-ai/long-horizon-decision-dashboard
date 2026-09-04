"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { glossaryEntries } from "@/lib/glossary-data";

export function GlossaryDrawer() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);
  const filtered = useMemo(() => {
    const key = query.trim().toLowerCase();
    if (!key) return glossaryEntries;
    return glossaryEntries.filter((entry) => [entry.term, ...entry.aliases, entry.category, entry.plain]
      .join(" ").toLowerCase().includes(key));
  }, [query]);

  useEffect(() => {
    if (!open) return;
    searchRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open]);

  useEffect(() => {
    const openFromTerm = (event: Event) => {
      setQuery((event as CustomEvent<string>).detail ?? "");
      setOpen(true);
    };
    window.addEventListener("glossary:open", openFromTerm);
    return () => window.removeEventListener("glossary:open", openFromTerm);
  }, []);

  return <>
    <button className="glossary-launcher" type="button" aria-expanded={open} aria-controls="glossary-drawer" onClick={() => setOpen(true)}>术语表</button>
    {open && <div className="glossary-layer">
      <button className="glossary-backdrop" type="button" aria-label="关闭术语表" onClick={() => setOpen(false)} />
      <aside id="glossary-drawer" className="glossary-drawer" role="dialog" aria-modal="true" aria-labelledby="glossary-title">
        <header><div><p className="eyebrow">PLAIN LANGUAGE</p><h2 id="glossary-title">术语表</h2></div><button type="button" aria-label="关闭术语表" onClick={() => setOpen(false)}>×</button></header>
        <label htmlFor="glossary-search">搜索中文、英文或缩写</label>
        <input ref={searchRef} id="glossary-search" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="例如：vintage、置信度、YCC" />
        <p className="glossary-count">找到 {filtered.length} 个词条</p>
        <div className="glossary-results">
          {filtered.map((entry) => <article key={entry.term}>
            <div><h3>{entry.term}</h3><span>{entry.category}</span></div>
            {entry.aliases.length > 0 && <small>{entry.aliases.join(" · ")}</small>}
            <p>{entry.plain}</p><p className="glossary-caution">注意：{entry.caution}</p>
          </article>)}
          {filtered.length === 0 && <p className="glossary-empty">没有找到。可以换一个更短的关键词。</p>}
        </div>
      </aside>
    </div>}
  </>;
}
