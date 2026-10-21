"use client";

import { useEffect, useEffectEvent, useState } from "react";
import { Search } from "lucide-react";
import { inputStyles } from "@/components/ui";

export const SEARCH_DELAY_MS = 350;

/** Search box that waits for a pause in typing before it updates the URL. */
export function SearchField({
  value,
  onSearch,
  placeholder = "Invoice no, member no or member name",
}: {
  value: string;
  onSearch: (value: string) => void;
  placeholder?: string;
}) {
  const [draft, setDraft] = useState({ text: value, source: value });
  if (draft.source !== value) setDraft({ text: value, source: value }); // follow outside changes (reset, top bar)

  const search = useEffectEvent((text: string) => onSearch(text));
  useEffect(() => {
    const text = draft.text.trim();
    if (text === value) return;
    const timer = setTimeout(() => search(text), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [draft.text, value]);

  return (
    <label className="flex flex-1 flex-col gap-1 text-[12px] font-medium text-muted lg:min-w-[260px]">
      Search
      <span className="relative">
        <Search size={16} aria-hidden className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-muted" />
        <input
          type="search"
          value={draft.text}
          maxLength={100}
          onChange={(e) => setDraft({ ...draft, text: e.target.value })}
          placeholder={placeholder}
          className={`${inputStyles} w-full pl-9`}
        />
      </span>
    </label>
  );
}
