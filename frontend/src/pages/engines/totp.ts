/**
 * The engine's CONTROL_TOTP_SECRET, made and checked in the browser only (PLAN §A32, TAA-923): it confirms
 * remote close/flatten on the engine machine and must never reach the server. RFC 6238 with SHA-1, 6 digits
 * and 30 s steps, as `pyotp` checks it on the engine; secrets are 32 base32 characters (160 bits), like
 * `python -m app.cli engine new-totp`.
 */

const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
export const STEP_SECONDS = 30;
export const DIGITS = 6;

export function toBase32(bytes: Uint8Array): string {
  let bits = 0;
  let value = 0;
  let out = '';
  for (const byte of bytes) {
    value = (value << 8) | byte;
    bits += 8;
    while (bits >= 5) {
      out += ALPHABET[(value >>> (bits - 5)) & 31] ?? '';
      bits -= 5;
    }
  }
  if (bits > 0) out += ALPHABET[(value << (5 - bits)) & 31] ?? '';
  return out;
}

export function fromBase32(text: string): Uint8Array {
  const clean = text.replace(/=+$/, '').toUpperCase();
  const out: number[] = [];
  let bits = 0;
  let value = 0;
  for (const char of clean) {
    const index = ALPHABET.indexOf(char);
    if (index < 0) throw new Error('not base32');
    value = (value << 5) | index;
    bits += 5;
    if (bits >= 8) {
      out.push((value >>> (bits - 8)) & 255);
      bits -= 8;
    }
  }
  return new Uint8Array(out);
}

/** A new secret from the browser's cryptographic random source. */
export function newSecret(): string {
  return toBase32(crypto.getRandomValues(new Uint8Array(20)));
}

/** The code for *secret* at the step holding *unixSeconds*. */
export async function totp(secret: string, unixSeconds: number): Promise<string> {
  const counter = Math.floor(unixSeconds / STEP_SECONDS);
  const message = new Uint8Array(8);
  new DataView(message.buffer).setBigUint64(0, BigInt(counter));
  const key = await crypto.subtle.importKey(
    'raw',
    fromBase32(secret).slice().buffer,
    { name: 'HMAC', hash: 'SHA-1' },
    false,
    ['sign'],
  );
  const mac = new Uint8Array(await crypto.subtle.sign('HMAC', key, message));
  const offset = (mac[mac.length - 1] ?? 0) & 15;
  const binary =
    (((mac[offset] ?? 0) & 0x7f) << 24) |
    ((mac[offset + 1] ?? 0) << 16) |
    ((mac[offset + 2] ?? 0) << 8) |
    (mac[offset + 3] ?? 0);
  return String(binary % 10 ** DIGITS).padStart(DIGITS, '0');
}

/** Whether *code* matches now or one step either side (clock drift), as the engine accepts it. */
export async function verifyCode(secret: string, code: string, unixSeconds: number): Promise<boolean> {
  if (!/^\d{6}$/.test(code)) return false;
  for (const drift of [0, -STEP_SECONDS, STEP_SECONDS]) {
    if ((await totp(secret, unixSeconds + drift)) === code) return true;
  }
  return false;
}

/** The authenticator-app URI (`provisioning_uri(secret, account="engine control", issuer="TAA engine")`). */
export function provisioningUri(secret: string, label: string): string {
  const issuer = encodeURIComponent('TAA engine');
  return `otpauth://totp/${issuer}:${encodeURIComponent(label)}?secret=${secret}&issuer=${issuer}`;
}
