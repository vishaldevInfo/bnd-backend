"use client";

// Filters live in the URL (?start=…&q=…) so a filtered view survives reloads,
// works with the back button and can be shared as a link.
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

export function useUrlParams() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const get = useCallback((key: string) => searchParams.get(key) ?? "", [searchParams]);

  /** Merge `changes` into the URL; empty values are removed. */
  const set = useCallback(
    (changes: Record<string, string | number | null>) => {
      const next = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(changes)) {
        if (value === null || value === "") next.delete(key);
        else next.set(key, String(value));
      }
      const query = next.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [router, pathname, searchParams],
  );

  return { get, set };
}

/** Reads a positive integer from the URL, falling back when missing or invalid. */
export function positiveInt(value: string, fallback: number, allowed?: number[]) {
  const number = Number(value);
  if (!Number.isInteger(number) || number < 1) return fallback;
  return allowed && !allowed.includes(number) ? fallback : number;
}
