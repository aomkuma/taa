import { applicationServerKey, deviceLabel, isIos } from './push';

const EDGE =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36 Edg/140.0';
const IPHONE =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1';
const ANDROID =
  'Mozilla/5.0 (Linux; Android 15) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Mobile Safari/537.36';
const MAC =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Safari/605.1.15';

describe('push helpers', () => {
  it('decodes the base64url VAPID key', () => {
    expect([...applicationServerKey('BAEC_w')]).toEqual([4, 1, 2, 255]);
  });

  it('names the device by browser and system', () => {
    expect(deviceLabel(EDGE)).toBe('Edge · Windows');
    expect(deviceLabel(IPHONE)).toBe('Safari · iOS');
    expect(deviceLabel(ANDROID)).toBe('Chrome · Android');
    expect(deviceLabel('curl/8')).toBe('Browser');
  });

  it('recognises iPhones and iPads that report a Mac', () => {
    expect(isIos({ userAgent: IPHONE, maxTouchPoints: 5 })).toBe(true);
    expect(isIos({ userAgent: MAC, maxTouchPoints: 5 })).toBe(true);
    expect(isIos({ userAgent: MAC, maxTouchPoints: 0 })).toBe(false);
  });
});
