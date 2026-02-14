/**
 * Local craving history store using localStorage + JSON.
 *
 * Persists craving log entries so the Cravings tab and Dashboard can
 * display history, patterns, and stats — same persistence pattern as
 * recipeStore.ts.
 */

import type { CravingHistoryEntry, CravingStats } from "@/types/api";
import { format } from "date-fns";

const STORAGE_KEY = "nutritwin-craving-history";
const CRAVING_STORE_EVENT = "craving-store-updated";

// --------------- internal helpers ---------------

function load(): CravingHistoryEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function save(entries: CravingHistoryEntry[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent(CRAVING_STORE_EVENT));
    }
  } catch (e) {
    console.error("Failed to save craving history", e);
  }
}

// --------------- public API ---------------

export function subscribeToCravingStore(callback: () => void): () => void {
  const handler = () => callback();
  window.addEventListener(CRAVING_STORE_EVENT, handler);
  return () => window.removeEventListener(CRAVING_STORE_EVENT, handler);
}

export function getCravingHistory(): CravingHistoryEntry[] {
  return load();
}

export function getRecentCravings(days: number): CravingHistoryEntry[] {
  const cutoff = Date.now() - days * 86_400_000;
  return load().filter((e) => new Date(e.timestamp).getTime() >= cutoff);
}

export function logCraving(params: {
  craving_text: string;
  flavor_type: string;
  mood?: string;
  time_of_day: string;
  context?: string;
}): CravingHistoryEntry {
  const entries = load();
  const entry: CravingHistoryEntry = {
    id: `crv-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    craving_text: params.craving_text,
    flavor_type: params.flavor_type,
    mood: params.mood,
    time_of_day: params.time_of_day,
    context: params.context,
    replacement_chosen: undefined,
    timestamp: format(new Date(), "yyyy-MM-dd'T'HH:mm:ss"),
  };
  entries.unshift(entry);
  save(entries);
  return entry;
}

export function markReplacementChosen(cravingId: string, replacementName: string): void {
  const entries = load();
  const entry = entries.find((e) => e.id === cravingId);
  if (entry) {
    entry.replacement_chosen = replacementName;
    save(entries);
  }
}

export function getCravingStats(): CravingStats {
  const entries = load();
  const total = entries.length;
  const replaced = entries.filter((e) => e.replacement_chosen).length;

  const flavorCounts: Record<string, number> = {};
  const moodCounts: Record<string, number> = {};
  const timeCounts: Record<string, number> = {};

  for (const e of entries) {
    flavorCounts[e.flavor_type] = (flavorCounts[e.flavor_type] || 0) + 1;
    if (e.mood) moodCounts[e.mood] = (moodCounts[e.mood] || 0) + 1;
    timeCounts[e.time_of_day] = (timeCounts[e.time_of_day] || 0) + 1;
  }

  const topOf = (counts: Record<string, number>) => {
    let max = 0;
    let key: string | null = null;
    for (const [k, v] of Object.entries(counts)) {
      if (v > max) { max = v; key = k; }
    }
    return key;
  };

  return {
    totalLogged: total,
    replacementsChosen: replaced,
    topFlavor: topOf(flavorCounts),
    topMood: topOf(moodCounts),
    topTime: topOf(timeCounts),
    replacementRate: total > 0 ? Math.round((replaced / total) * 100) : 0,
  };
}
