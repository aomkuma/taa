import { gaugeFill, gaugeLevel, lossUsed } from './gaugeLevels';

describe('gauge levels', () => {
  it('grades the share of the limit used', () => {
    expect(gaugeLevel(0.4, 2)).toBe('ok');
    expect(gaugeLevel(1, 2)).toBe('warn');
    expect(gaugeLevel(1.6, 2)).toBe('danger');
    expect(gaugeLevel(2, 2)).toBe('breached');
    expect(gaugeLevel(null, 2)).toBe('unknown');
    expect(gaugeLevel(Number.NaN, 2)).toBe('unknown');
  });

  it('clamps the drawn fill', () => {
    expect(gaugeFill(1, 2)).toBe(50);
    expect(gaugeFill(5, 2)).toBe(100);
    expect(gaugeFill(-1, 2)).toBe(0);
    expect(gaugeFill(null, 2)).toBe(0);
  });

  it('counts only losses against a loss limit', () => {
    expect(lossUsed(-0.75)).toBe(0.75);
    expect(lossUsed(1.2)).toBe(0);
    expect(lossUsed(null)).toBeNull();
  });
});
