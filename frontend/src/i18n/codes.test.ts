import enumsPy from '../../../app/core/enums.py?raw';
import lifecyclePy from '../../../app/advisory/lifecycle.py?raw';
import shadowPy from '../../../app/advisory/shadow.py?raw';
import statusesPy from '../../../app/advisory/statuses.py?raw';
import suitabilityPy from '../../../app/advisory/suitability.py?raw';
import reasonsPy from '../../../app/risk/reasons.py?raw';
import signalModelsPy from '../../../app/strategy/signal_models.py?raw';
import enginesPy from '../../../app/web/engines.py?raw';
import orderManagerPy from '../../../app/engine/order_manager.py?raw';
import circuitBreakerPy from '../../../app/risk/circuit_breaker.py?raw';
import notificationsPy from '../../../app/sync/notifications.py?raw';
import decisionEnginePy from '../../../app/engine/decision_engine.py?raw';
import frameworkPy from '../../../app/evidence/framework.py?raw';
import strategiesPy from '../../../app/web/strategies.py?raw';
import commandQueuePy from '../../../app/sync/command_queue.py?raw';
import exampleStrategyPy from '../../../app/strategy/example_strategy.py?raw';
import setupsPy from '../../../app/strategy/setups.py?raw';

import { createI18n } from '@/i18n';
import {
  BREAKER_NAMES,
  codeKey,
  COMMAND_STATUSES,
  STRATEGY_NAMES,
  STRATEGY_STATES,
  CODES_NAMESPACE,
  DECISIONS,
  FAMILIES,
  REGIMES,
  SESSIONS,
  TRENDS,
  VOLATILITY_STATES,
  ENGINE_ERRORS,
  EXIT_REASONS,
  GATE_STATUSES,
  GATES,
  INVALID_REASONS,
  NOTIFICATION_TYPES,
  ORDER_STATES,
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
    expect(translateCode(createI18n('th'), 'reason', 'NOT_A_CODE:x')).toBe('NOT_A_CODE:x');
  });

  it('renders a translated code with its detail', () => {
    expect(translateCode(createI18n('th'), 'reason', 'BREAKER_OPEN:daily_loss')).toBe(
      'เบรกเกอร์ทำงาน: daily_loss',
    );
    expect(translateCode(createI18n('en'), 'reason', 'ORDER_CHECK_FAILED:10019')).toBe(
      'Broker order check failed: 10019',
    );
    const i18n = createI18n('th');
    i18n.addResourceBundle('th', CODES_NAMESPACE, { reason: { NEW_CODE: 'ใหม่: {{detail}}' } });
    expect(translateCode(i18n, 'reason', 'NEW_CODE:a:b')).toBe('ใหม่: a:b');
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
    ['Trend', enumsPy, TRENDS],
    ['Regime', enumsPy, REGIMES],
    ['VolatilityState', enumsPy, VOLATILITY_STATES],
    ['Session', enumsPy, SESSIONS],
    ['IntentState', orderManagerPy, ORDER_STATES],
    ['StrategyState', strategiesPy, STRATEGY_STATES],
    ['QueueStatus', commandQueuePy, COMMAND_STATUSES],
  ] as const)('%s', (className, source, values) => {
    expect(sorted(values)).toEqual(sorted(pyStrEnumValues(source, className)));
  });
});

describe('strategy names match the catalog', () => {
  it('every strategy class of example_strategy.py and setups.py', () => {
    const names = [exampleStrategyPy, setupsPy].flatMap((source) =>
      [...source.matchAll(/^ {4}name = "([a-z0-9_]+)"\r?$/gm)].map((m) => m[1] ?? ''),
    );
    expect(names.length).toBeGreaterThan(5);
    expect(sorted(STRATEGY_NAMES)).toEqual(sorted(names));
  });
});

describe('code texts', () => {
  it.each([
    ['engine', ENGINE_ERRORS],
    ['breaker', BREAKER_NAMES],
    ['notificationType', NOTIFICATION_TYPES],
    ['decision', DECISIONS],
    ['family', FAMILIES],
    ['trend', TRENDS],
    ['regime', REGIMES],
    ['volatility', VOLATILITY_STATES],
    ['session', SESSIONS],
    ['orderState', ORDER_STATES],
    ['reason', REASON_CODES],
    ['exitReason', EXIT_REASONS],
    ['strategyState', STRATEGY_STATES],
    ['commandStatus', COMMAND_STATUSES],
    ['strategy', STRATEGY_NAMES],
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
