import { encode } from 'uqr';

/**
 * A QR code drawn as one SVG path (CSP-safe, no innerHTML), from the bundled MIT-licensed `uqr` encoder.
 * Dark modules on a white quiet zone, whatever the theme, so phone cameras read it.
 */
export function QrCode({ value, label }: { value: string; label: string }) {
  const { data, size } = encode(value, { ecc: 'M', border: 0 });
  const quiet = 4;
  const total = size + 2 * quiet;
  let path = '';
  data.forEach((row, y) => {
    row.forEach((dark, x) => {
      if (dark) path += `M${String(x + quiet)} ${String(y + quiet)}h1v1h-1z`;
    });
  });
  return (
    <svg
      role="img"
      aria-label={label}
      viewBox={`0 0 ${String(total)} ${String(total)}`}
      shapeRendering="crispEdges"
      className="h-48 w-48 bg-white"
    >
      <rect width={total} height={total} fill="#ffffff" />
      <path d={path} fill="#000000" />
    </svg>
  );
}
