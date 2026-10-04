import enumsPy from '../../../app/core/enums.py?raw';
import lifecyclePy from '../../../app/advisory/lifecycle.py?raw';
import shadowPy from '../../../app/advisory/shadow.py?raw';
import statusesPy from '../../../app/advisory/statuses.py?raw';
import suitabilityPy from '../../../app/advisory/suitability.py?raw';
import reasonsPy from '../../../app/risk/reasons.py?raw';
import signalModelsPy from '../../../app/strategy/signal_models.py?raw';
import enginesPy from '../../../app/web/engines.py?raw';
import circuitBreakerPy from '../../../app/risk/circuit_breaker.py?raw';
import notificationsPy from '../../../app/sync/notifications.py?raw';
import decisionEnginePy from '../../../app/engine/decision_engine.py?raw';
import frameworkPy from '../../../app/evidence/framework.py?raw';

import { createI18n } from '@/i18n';
import {
  BREAKER_NAMES,
  codeKey,
  CODES_NAMESPACE,
  DECISIONS,
  FAMILIES,
  ENGINE_ERRORS,
  EXIT_REASONS,
  GATE_STATUSES,
  GATES,
  INVALID_REASONS,
  NOTIFICATION_TYPES,
  OPPORTUNITY_STATUSES,
  parseCode,
  REASON_CODES,
  SHADOW_STATUSES,
  translateCode,
  WINDOW_REASONS,
} from '@/i18n/codes';
import { pyStrEnumValues } from '@/test/python';

const sorted = (values: Iterable<string>) => [...values].sort();

describe('code key scheme', () => {
  it('splits parameterized codes at the first colon', () => {
    expect(parseCode('BREAKER_OPEN:daily_loss')).toEqual({ code: 'BREAKER_OPEN', detail: 'daily_loss' });
    expect(parseCode('ORDER_CHECK_FAILED:10019:x')).toEqual({
      code: 'ORDER_CHECK_FAILED',
      detail: '10019:x',
    });
    expect(parseCode('NO_SETUP')).toEqual({ code: 'NO_SETUP', detail: null });
  });

  it('builds namespaced keys from the bare code', () => {
    expect(codeKey('reason', 'BREAKER_OPEN:daily_loss')).toBe('codes:reason.BREAKER_OPEN');
    expect(codeKey('opportunityStatus', 'EXPIRED')).toBe('codes:opportunityStatus.EXPIRED');
  });

  it('renders an untranslated code as the raw code', () => {
    expect(translateCode(createI18n('th'), 'reason', 'BREAKER_OPEN:daily_loss')).toBe(
      'BREAKER_OPEN:daily_loss',
    );
  });

  it('renders a translated code with its detail', () => {
    const i18n = createI18n('th');
    i18n.addResourceBundle('th', CODES_NAMESPACE, { reason: { BREAKER_OPEN: 'เบรกเกอร์ทำงาน: {{detail}}' } });
    expect(translateCode(i18n, 'reason', 'BREAKER_OPEN:daily_loss')).toBe('เบรกเกอร์ทำงาน: daily_loss');
  });
});

describe('code lists match the backend enums', () => {
  it('reason codes = Reason ∪ ReasonCode', () => {
    const backend = new Set([
      ...pyStrEnumValues(reasonsPy, 'Reason'),
      ...pyStrEnumValues(signalModelsPy, 'ReasonCode'),
    ]);
    expect(backend.size).toBeGreaterThan(50);
    expect(sorted(REASON_CODES)).toEqual(sorted(backend));
    expect(new Set(REASON_CODES).size).toBe(REASON_CODES.length);
  });

  it.each([
    ['Gate', suitabilityPy, GATES],
    ['GateStatus', suitabilityPy, GATE_STATUSES],
    ['OpportunityStatus', statusesPy, OPPORTUNITY_STATUSES],
    ['WindowReason', lifecyclePy, WINDOW_REASONS],
    ['InvalidReason', lifecyclePy, INVALID_REASONS],
    ['ShadowStatus', shadowPy, SHADOW_STATUSES],
    ['ExitReason', enumsPy, EXIT_REASONS],
    ['EngineErrorCode', enginesPy, ENGINE_ERRORS],
    ['BreakerName', circuitBreakerPy, BREAKER_NAMES],
    ['NotificationType', notificationsPy, NOTIFICATION_TYPES],
    ['Decision', decisionEnginePy, DECISIONS],
    ['Family', frameworkPy, FAMILIES],
  ] as const)('%s', (className, source, values) => {
    expect(sorted(values)).toEqual(sorted(pyStrEnumValues(source, className)));
  });
});

describe('code texts', () => {
  it.each([
    ['engine', ENGINE_ERRORS],
    ['breaker', BREAKER_NAMES],
    ['notificationType', NOTIFICATION_TYPES],
    ['decision', DECISIONS],
    ['family', FAMILIES],
  ] as const)('every %s code has a text in both languages', (kind, codes) => {
    for (const language of ['th', 'en'] as const) {
      const i18n = createI18n(language);
      for (const code of codes) {
        expect(i18n.exists(codeKey(kind, code)), `${language} ${code}`).toBe(true);
        expect(translateCode(i18n, kind, code)).not.toBe(code);
      }
    }
  });
});
