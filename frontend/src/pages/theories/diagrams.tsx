/**
 * One schematic sketch per theory family (CSP-safe inline SVG, 120×60): price as a line, the theory's
 * levels or shapes in the muted ink. They illustrate the idea only; they are not data.
 */
import type { ReactNode } from 'react';

const PRICE = 'fill-none stroke-sky-700 dark:stroke-sky-400';
const GUIDE = 'fill-none stroke-slate-400 dark:stroke-slate-500';
const AREA = 'fill-slate-300/50 stroke-none dark:fill-slate-600/40';
const LABEL = 'fill-slate-500 text-[7px] dark:fill-slate-400';

const price = (points: string) => <polyline points={points} className={PRICE} strokeWidth={1.5} />;
const dashed = (x1: number, y1: number, x2: number, y2: number, key?: string) => (
  <line key={key} x1={x1} y1={y1} x2={x2} y2={y2} className={GUIDE} strokeDasharray="3 2" />
);
const label = (x: number, y: number, text: string) => (
  <text key={`${text}-${String(x)}`} x={x} y={y} className={LABEL}>
    {text}
  </text>
);

function candle(x: number, open: number, close: number, high: number, low: number) {
  const up = close < open; // smaller y is higher
  return (
    <g key={x}>
      <line x1={x} x2={x} y1={high} y2={low} className={GUIDE} />
      <rect
        x={x - 3}
        y={Math.min(open, close)}
        width={6}
        height={Math.max(Math.abs(open - close), 1)}
        className={up ? 'fill-sky-600 dark:fill-sky-400' : 'fill-slate-500'}
      />
    </g>
  );
}

const SKETCHES: Record<string, ReactNode> = {
  FIBONACCI: (
    <>
      {[10, 22, 30, 37, 52].map((y, i) => dashed(40, y, 118, y, `f${String(i)}`))}
      {label(100, 35, '61.8%')}
      {price('4,54 40,52 70,10 92,37 118,12')}
    </>
  ),
  LEVELS: (
    <>
      <rect x={2} y={40} width={116} height={8} className={AREA} />
      {price('2,20 20,42 34,14 54,41 72,18 92,40 118,12')}
    </>
  ),
  TREND: (
    <>
      {dashed(6, 54, 116, 22)}
      {price('6,52 22,36 34,46 52,26 64,38 84,16 96,28 116,8')}
    </>
  ),
  CHART_PATTERN: (
    <>
      {dashed(4, 24, 116, 24)}
      {label(4, 21, 'W')}
      {price('4,10 26,48 44,24 64,48 84,24 116,6')}
    </>
  ),
  CANDLESTICK: (
    <>
      {candle(20, 18, 30, 14, 34)}
      {candle(36, 26, 40, 22, 44)}
      {candle(52, 38, 46, 34, 52)}
      {candle(68, 48, 22, 18, 52)}
      {candle(84, 24, 14, 10, 28)}
      {candle(100, 16, 8, 4, 20)}
    </>
  ),
  MOMENTUM: (
    <>
      {price('4,28 30,12 46,22 74,6 90,18')}
      {dashed(30, 12, 74, 6)}
      <polyline points="4,52 30,36 46,48 74,44 90,54" className={GUIDE} strokeWidth={1.2} />
      {dashed(30, 36, 74, 44)}
      {label(94, 46, 'RSI')}
    </>
  ),
  VOLATILITY_VOLUME: (
    <>
      <path d="M2 14 C30 22, 50 26, 70 26 L70 34 C50 34, 30 38, 2 46 Z" className={AREA} />
      {price('2,30 20,28 40,31 58,29 70,30 86,18 104,10 118,6')}
    </>
  ),
  ICHIMOKU: (
    <>
      <path d="M2 50 C30 46, 60 40, 118 34 L118 46 C60 52, 30 56, 2 58 Z" className={AREA} />
      {price('2,40 24,44 44,30 70,26 92,16 118,10')}
    </>
  ),
  SMART_MONEY: (
    <>
      {dashed(2, 44, 70, 44)}
      <rect x={66} y={22} width={24} height={8} className={AREA} />
      {label(92, 28, 'FVG')}
      {price('2,30 24,44 40,34 56,52 66,40 76,22 90,28 118,8')}
    </>
  ),
  HARMONIC: (
    <>
      {price('4,52 30,10 52,34 78,16 108,46')}
      {label(2, 58, 'X')}
      {label(28, 8, 'A')}
      {label(50, 42, 'B')}
      {label(76, 13, 'C')}
      {label(110, 54, 'D')}
    </>
  ),
  ELLIOTT: (
    <>
      {price('4,54 22,36 32,44 58,14 70,26 96,8 118,30')}
      {label(20, 33, '1')}
      {label(30, 52, '2')}
      {label(56, 11, '3')}
      {label(68, 34, '4')}
      {label(94, 6, '5')}
    </>
  ),
  SESSIONS: (
    <>
      <rect x={4} y={26} width={52} height={14} className={AREA} />
      {price('4,34 14,28 24,38 34,29 44,37 56,32 72,22 92,14 118,8')}
    </>
  ),
};

export function FamilyDiagram({ family, label: name }: { family: string; label: string }) {
  const sketch = SKETCHES[family];
  if (sketch === undefined) return null;
  return (
    <svg viewBox="0 0 120 60" role="img" aria-label={name} className="h-16 w-32 shrink-0">
      {sketch}
    </svg>
  );
}
