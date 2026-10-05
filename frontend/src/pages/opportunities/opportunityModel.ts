/** Pure helpers of the opportunities page (PLAN §A26 windows and statuses, §A29 explainable %). */
import type { Contribution, EvidenceRef, Opportunity, Scoreboard } from './schemas';

/** EXPIRING is derived here: an open opportunity with less than this share of its window left (§A26). */
export const EXPIRING_SHARE = 0.2;
const OPEN = new Set(['CANDIDATE', 'ACTIVE']);

export interface WindowState {
  /** An `OpportunityStatus`, or EXPIRING (derived here). */
  status: string;
  /** Milliseconds left in the window (open opportunities with a window), else null. */
  remainingMs: number | null;
}

/**
 * The status to show at *now* (server time): an open opportunity past its window shows EXPIRED before the
 * engine's next lifecycle pass marks it so; the last 20% of the window shows EXPIRING.
 */
export function windowState(
  o: Pick<Opportunity, 'status' | 'created_at' | 'valid_until'>,
  now: number,
): WindowState {
  if (!OPEN.has(o.status) || o.valid_until === null) return { status: o.status, remainingMs: null };
  const end = Date.parse(o.valid_until);
  const start = Date.parse(o.created_at);
  const remainingMs = end - now;
  if (remainingMs <= 0) return { status: 'EXPIRED', remainingMs: 0 };
  const total = end - start;
  const expiring = total > 0 && remainingMs < total * EXPIRING_SHARE;
  return { status: expiring ? 'EXPIRING' : o.status, remainingMs };
}

/** `mm:ss`, or `h:mm:ss` from an hour up. */
export function countdown(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const two = (n: number) => String(n).padStart(2, '0');
  return h > 0 ? `${String(h)}:${two(m)}:${two(s)}` : `${two(m)}:${two(s)}`;
}

/** The reason code kind of a terminal status (`status_reason`), for `codes:` texts. */
export function reasonKind(status: string): 'windowReason' | 'invalidReason' | null {
  if (status === 'EXPIRED') return 'windowReason';
  if (status === 'INVALIDATED') return 'invalidReason';
  return null;
}

/** Open opportunities first (soonest window end first), then the rest newest first. */
export function sortForCards(items: readonly Opportunity[], now: number): Opportunity[] {
  const open = (o: Opportunity) =>
    windowState(o, now).remainingMs !== null && windowState(o, now).status !== 'EXPIRED';
  return [...items].sort((a, b) => {
    const oa = open(a);
    const ob = open(b);
    if (oa !== ob) return oa ? -1 : 1;
    if (oa && ob) return Date.parse(a.valid_until ?? '') - Date.parse(b.valid_until ?? '');
    return Date.parse(b.created_at) - Date.parse(a.created_at);
  });
}

/** The number of ACTIVE opportunities still inside their window: the app icon badge (R25). */
export function activeCount(items: readonly Opportunity[], now: number): number {
  return items.filter((o) => {
    const s = windowState(o, now).status;
    return o.status === 'ACTIVE' && (s === 'ACTIVE' || s === 'EXPIRING');
  }).length;
}

/** Contributions split into supporting (raise the %) and conflicting (lower it), largest first. */
export function splitContributions(contributions: readonly Contribution[]): {
  supporting: Contribution[];
  conflicting: Contribution[];
} {
  const sorted = [...contributions].sort((a, b) => Math.abs(b.points) - Math.abs(a.points));
  return {
    supporting: sorted.filter((c) => c.points > 0),
    conflicting: sorted.filter((c) => c.points < 0),
  };
}

export interface TrackRecord {
  n: number;
  hitRate: number;
  expectancyR: number | null;
}

/** A theory's hypothetical record for this opportunity's asset class and timeframe (scoreboard `ev:` rows). */
export function trackRecord(
  scoreboard: Scoreboard | undefined,
  feature: string,
  assetClass: string,
  timeframe: string,
): TrackRecord | null {
  const row = scoreboard?.items.find(
    (i) =>
      i.theory === feature && i.level === 'detector' && i.group[0] === assetClass && i.group[1] === timeframe,
  );
  return row ? { n: row.n, hitRate: row.hit_rate, expectancyR: row.expectancy_r } : null;
}

/** Evidence grouped by relation: supporting, conflicting, then neutral. */
export function evidenceByRelation(
  evidence: readonly EvidenceRef[],
): Record<'SUPPORTS' | 'CONFLICTS' | 'NEUTRAL', EvidenceRef[]> {
  const out: Record<'SUPPORTS' | 'CONFLICTS' | 'NEUTRAL', EvidenceRef[]> = {
    SUPPORTS: [],
    CONFLICTS: [],
    NEUTRAL: [],
  };
  for (const e of evidence) {
    const key = e.relation === 'SUPPORTS' || e.relation === 'CONFLICTS' ? e.relation : 'NEUTRAL';
    out[key].push(e);
  }
  for (const list of Object.values(out))
    list.sort((a, b) => b.item.evidence.quality - a.item.evidence.quality);
  return out;
}

/** The number of theory families among the supporting evidence (the "minimum supporting theories" rule). */
export function supportingFamilies(evidence: readonly EvidenceRef[]): number {
  return new Set(evidence.filter((e) => e.relation === 'SUPPORTS').map((e) => e.item.evidence.family)).size;
}

/** The chart of the opportunity's symbol on *timeframe*, with its evidence overlaid (charts page, TAA-905). */
export function chartLink(symbol: string, opportunityId: string, timeframe: string): string {
  const q = new URLSearchParams({ symbol, opportunity: opportunityId, tf: timeframe });
  return `/charts?${q.toString()}`;
}
