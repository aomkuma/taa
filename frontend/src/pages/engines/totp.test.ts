import { fromBase32, newSecret, provisioningUri, toBase32, totp, verifyCode } from './totp';

// Reference codes printed by pyotp (the engine's checker): pyotp.TOTP(SECRET).at(t)
const SECRET = 'JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP';

describe('control TOTP in the browser', () => {
  it('matches pyotp', async () => {
    expect(await totp(SECRET, 1_700_000_000)).toBe('406058');
    expect(await totp(SECRET, 59)).toBe('503347');
  });

  it('accepts one step of drift either way, like the engine', async () => {
    const now = 1_700_000_000;
    expect(await verifyCode(SECRET, '406058', now + 30)).toBe(true);
    expect(await verifyCode(SECRET, '406058', now + 90)).toBe(false);
    expect(await verifyCode(SECRET, '40605', now)).toBe(false);
  });

  it('makes 160-bit base32 secrets and the authenticator URI', () => {
    const secret = newSecret();
    expect(secret).toMatch(/^[A-Z2-7]{32}$/);
    expect(newSecret()).not.toBe(secret);
    expect(toBase32(fromBase32(SECRET))).toBe(SECRET);
    expect(provisioningUri(SECRET, 'home pc')).toBe(
      `otpauth://totp/TAA%20engine:home%20pc?secret=${SECRET}&issuer=TAA%20engine`,
    );
  });
});
