import samples from '@/test/fixtures/api-samples.json';

import {
  breakdownRows,
  bucketRows,
  calibrationPoints,
  curveSeries,
  scoreGroups,
  theoryParts,
  wilson,
} from './accuracyModel';
import { AccuracySchema, CalibrationSchema } from './schemas';

// Real responses recorded by tests/web/test_api_samples.py.
const recorded = samples as Record<string, unknown>;
const accuracy = AccuracySchema.parse(recorded['engines/ENGINE/accuracy']);
const calibration = CalibrationSchema.parse(recorded['engines/ENGINE/calibration']);

describe('intervals', () => {
  it('matches the backend Wilson interval of the samples', () => {
    const s = accuracy.live.summary;
    const [low, high] = wilson(s.wins, s.n) ?? [Number.NaN, Number.NaN];
    expect(100 * low).toBeCloseTo(s.hit_low ?? Number.NaN, 6);
    expect(100 * high).toBeCloseTo(s.hit_high ?? Number.NaN, 6);
    expect(wilson(0, 0)).toBeNull();
  });

  it('turns reliability bins with outcomes into points with intervals', () => {
    const points = calibrationPoints(calibration.reliability);
    expect(points.length).toBe(calibration.reliability.filter((b) => b.n > 0).length);
    for (const p of points) {
      expect(p.low).toBeLessThanOrEqual(p.observed);
      expect(p.high).toBeGreaterThanOrEqual(p.observed);
    }
  });
});

describe('breakdowns', () => {
  it('orders strength buckets from the weakest and groups by size', () => {
    const summary = accuracy.live.summary;
    expect(
      bucketRows({ '80+': summary, '50-65': summary, '<50': summary, '65-80': summary }).map(([k]) => k),
    ).toEqual(['<50', '50-65', '65-80', '80+']);
    expect(breakdownRows(accuracy.live.breakdowns.symbol).map(([k, s]) => [k, s.n])).toEqual([
      ['EURUSD', 2],
      ['XAUUSD', 2],
      ['GBPUSD', 1],
    ]);
    expect(breakdownRows(undefined)).toEqual([]);
  });
});

describe('curve', () => {
  it('keeps one point per second, the last value winning', () => {
    const at = '2026-09-25T11:00:00+00:00';
    const point = { at, pnl: 1, r: 0.1, drawdown: 0, drawdown_r: 0 };
    expect(curveSeries([point, { ...point, pnl: 3 }], (p) => p.pnl)).toEqual([
      { time: Date.parse(at) / 1000, value: 3 },
    ]);
    expect(curveSeries(accuracy.live.curve, (p) => p.r)).toHaveLength(5);
  });
});

describe('scoreboard', () => {
  it('splits detector names and groups by asset class and timeframe', () => {
    expect(theoryParts({ theory: 'ev:FIBONACCI:fib.retracement', level: 'detector' })).toEqual({
      family: 'FIBONACCI',
      detector: 'fib.retracement',
    });
    expect(theoryParts({ theory: 'FIBONACCI', level: 'family' })).toEqual({
      family: 'FIBONACCI',
      detector: null,
    });
    const groups = scoreGroups(accuracy.live.scoreboard, 'family');
    expect(groups.map((g) => [g.assetClass, g.timeframe])).toEqual([
      ['FOREX_MAJOR', 'M15'],
      ['METAL', 'M15'],
    ]);
    expect(groups.every((g) => g.rows.every((r) => r.level === 'family'))).toBe(true);
  });
});
