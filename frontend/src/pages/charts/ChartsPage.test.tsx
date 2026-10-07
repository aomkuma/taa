import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { apiError, json } from '@/test/api';
import { heartbeat, iso, owner, renderShell, status } from '@/test/engine';
import { streamEvent } from '@/test/eventSource';
import samples from '@/test/fixtures/api-samples.json';

import type { ChartModel } from './model';

// jsdom has no canvas: record what the page asks the chart to draw instead.
const drawn: { models: ChartModel[]; themes: boolean[]; destroyed: number } = {
  models: [],
  themes: [],
  destroyed: 0,
};
vi.mock('./chartAdapter', () => ({
  createPriceChart: (_el: HTMLElement, theme: { dark: boolean }) => {
    drawn.themes.push(theme.dark);
    return {
      update: (model: ChartModel) => drawn.models.push(model),
      setTheme: (next: { dark: boolean }) => drawn.themes.push(next.dark),
      destroy: () => {
        drawn.destroyed += 1;
      },
    };
  },
}));

const T0 = Date.parse('2026-09-30T10:00:00Z');
// a real account snapshot (tests/web/test_api_samples.py), to carry the bot's positions
const ACCOUNT = (
  (samples as Record<string, Record<string, unknown>>)['engines/ENGINE/status']?.heartbeat as {
    account: Record<string, unknown>;
  }
).account;
const bars = Array.from({ length: 4 }, (_, i) => [iso(T0 + i * 900_000), 1.1, 1.102, 1.098, 1.101, 10]);

function candles(symbol = 'EURUSD') {
  return {
    server: 'FBS-Demo',
    symbol,
    timeframe: 'M15',
    bars,
    overlays: {},
    markers: [],
    zones: [{ low: 1.098, high: 1.099, touches: 3, role: 'SUPPORT' }],
  };
}

const decision = {
  decision_id: 'd1',
  symbol: 'XAUUSD',
  signal: {
    symbol: 'XAUUSD',
    timeframe: 'H1',
    action: 'SELL',
    entry_price: 2600,
    stop_loss: 2610,
    take_profit: 2580,
    evidence: [
      {
        relation: 'SUPPORTS',
        item: {
          evidence: {
            evidence_id: 'e1',
            detector_id: 'fib.retracement',
            family: 'FIBONACCI',
            name: 'Fibonacci retracement',
            i18n_key: 'evidence.fib.retracement',
            timeframe: 'H1',
            direction: 'BEAR',
            detected_at: iso(T0),
            quality: 0.7,
            key_levels: [{ name: 'fib_61.8', price: 2605, at: null }],
            invalidation: null,
            targets: [],
          },
        },
      },
      {
        relation: 'CONFLICTS',
        item: {
          evidence: {
            evidence_id: 'e2',
            detector_id: 'levels.donchian',
            family: 'LEVELS',
            name: 'Donchian breakout',
            i18n_key: 'evidence.levels.donchian',
            timeframe: 'H1',
            direction: 'BULL',
            detected_at: iso(T0),
            quality: 0.9,
            key_levels: [{ name: 'channel_20', price: 2620, at: null }],
            invalidation: 2590,
            targets: [],
          },
        },
      },
    ],
  },
};

const lastModel = () => {
  const model = drawn.models.at(-1);
  if (!model) throw new Error('nothing drawn');
  return model;
};

function setup(extra: Record<string, () => Response> = {}) {
  const api = owner({
    'GET /engines/e1/symbols?enabled=true': () =>
      json({
        items: [
          { symbol: 'EURUSD', enabled: true, asset_class: 'FX_MAJOR', reason: '', description: 'Euro' },
          { symbol: 'XAUUSD', enabled: true, asset_class: 'METAL', reason: '', description: 'Gold' },
        ],
      }),
    'GET /engines/e1/candles?symbol=EURUSD&timeframe=M15&limit=300&overlays=ema:20,ema:50,rsi:14&zones=true':
      () => json(candles()),
    'GET /engines/e1/positions?status=OPEN&limit=200': () =>
      json({
        items: [
          {
            ticket: 7,
            symbol: 'EURUSD',
            side: 'BUY',
            volume: 0.1,
            entry_price: 1.1,
            entry_time: iso(T0),
            sl: 1.095,
            tp: 1.11,
            price_current: 1.101,
          },
        ],
        next_cursor: null,
      }),
    ...extra,
  });
  return api;
}

describe('charts page', () => {
  beforeEach(() => {
    drawn.models = [];
    drawn.themes = [];
    drawn.destroyed = 0;
  });

  it('draws the first symbol with the default indicators, zones and open-position lines', async () => {
    setup();
    renderShell('/charts');
    expect(await screen.findByRole('heading', { name: 'Charts' })).toBeInTheDocument();
    await waitFor(() => {
      expect(drawn.models.length).toBeGreaterThan(0);
    });
    const model = lastModel();
    expect(model.candles).toHaveLength(4);
    expect(model.priceLines.map((p) => p.title)).toEqual(['Support ×3', '#7 BUY', 'SL #7', 'TP #7']);
    expect(screen.getByRole('link', { name: 'TradingView Lightweight Charts™' })).toHaveAttribute(
      'href',
      'https://www.tradingview.com/',
    );
  });

  it('asks for other overlays and no zones when the toggles change', async () => {
    const api = setup({
      'GET /engines/e1/candles?symbol=EURUSD&timeframe=M15&limit=300&overlays=ema:20,ema:50,rsi:14': () =>
        json(candles()),
      'GET /engines/e1/candles?symbol=EURUSD&timeframe=M15&limit=300&overlays=ema:20,ema:50,rsi:14,adx:14':
        () => json(candles()),
    });
    const user = userEvent.setup();
    renderShell('/charts');
    await waitFor(() => {
      expect(drawn.models.length).toBeGreaterThan(0);
    });
    await user.click(screen.getByRole('checkbox', { name: 'S/R zones' }));
    await user.click(screen.getByRole('checkbox', { name: 'ADX 14' }));
    await waitFor(() => {
      expect(api.calls.map((c) => c.path)).toContain(
        '/engines/e1/candles?symbol=EURUSD&timeframe=M15&limit=300&overlays=ema:20,ema:50,rsi:14,adx:14',
      );
    });
    await waitFor(() => {
      expect(lastModel().priceLines.some((p) => p.title.startsWith('Support'))).toBe(false);
    });
  });

  it('switches symbol and timeframe through the URL', async () => {
    const api = setup({
      'GET /engines/e1/candles?symbol=XAUUSD&timeframe=H1&limit=300&overlays=ema:20,ema:50,rsi:14&zones=true':
        () => json(candles('XAUUSD')),
    });
    const user = userEvent.setup();
    const { router } = renderShell('/charts');
    await waitFor(() => {
      expect(drawn.models.length).toBeGreaterThan(0);
    });
    await user.click(screen.getByRole('combobox', { name: 'Symbol' }));
    await user.keyboard('xau');
    expect(
      within(screen.getByRole('listbox'))
        .getAllByRole('option')
        .map((o) => o.textContent),
    ).toEqual(['XAUUSD']);
    await user.click(screen.getByRole('option', { name: 'XAUUSD' }));
    await user.selectOptions(screen.getByRole('combobox', { name: 'Timeframe' }), 'H1');
    expect(router.state.location.search).toBe('?symbol=XAUUSD&tf=H1');
    await waitFor(() => {
      expect(api.calls.map((c) => c.path)).toContain(
        '/engines/e1/candles?symbol=XAUUSD&timeframe=H1&limit=300&overlays=ema:20,ema:50,rsi:14&zones=true',
      );
    });
  });

  it('opens a symbol that has candles and lists the charted symbols first', async () => {
    const api = setup({
      'GET /engines/e1/backtests/history': () =>
        json({
          items: [
            {
              server: 'FBS-Demo',
              symbol: 'XAUUSD',
              timeframe: 'M15',
              first: iso(T0),
              last: iso(T0),
              bars: 4,
            },
          ],
        }),
      'GET /engines/e1/candles?symbol=XAUUSD&timeframe=M15&limit=300&overlays=ema:20,ema:50,rsi:14&zones=true':
        () => json(candles('XAUUSD')),
    });
    const user = userEvent.setup();
    renderShell('/charts');
    const input = await screen.findByRole('combobox', { name: 'Symbol' });
    await waitFor(() => {
      expect(input).toHaveValue('XAUUSD');
    });
    expect(api.calls.map((c) => c.path)).not.toContain(
      '/engines/e1/candles?symbol=EURUSD&timeframe=M15&limit=300&overlays=ema:20,ema:50,rsi:14&zones=true',
    );
    await user.click(input);
    expect(
      within(screen.getByRole('listbox'))
        .getAllByRole('option')
        .map((o) => o.textContent),
    ).toEqual(['XAUUSDchart', 'EURUSD']);
    await user.keyboard('zzz');
    expect(screen.getByText('No matching symbol')).toBeInTheDocument();
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    expect(input).toHaveValue('XAUUSD');
  });

  it('picks a symbol with the keyboard', async () => {
    setup({
      'GET /engines/e1/candles?symbol=XAUUSD&timeframe=M15&limit=300&overlays=ema:20,ema:50,rsi:14&zones=true':
        () => json(candles('XAUUSD')),
    });
    const user = userEvent.setup();
    const { router } = renderShell('/charts');
    await waitFor(() => {
      expect(drawn.models.length).toBeGreaterThan(0);
    });
    await user.click(screen.getByRole('combobox', { name: 'Symbol' }));
    await user.keyboard('{ArrowDown}{Enter}');
    expect(router.state.location.search).toBe('?symbol=XAUUSD');
  });

  it('opens a decision focused on its supporting evidence and adds items from the list', async () => {
    setup({
      'GET /engines/e1/decisions/d1': () => json(decision),
      // no S/R zones while a signal is shown
      'GET /engines/e1/candles?symbol=XAUUSD&timeframe=H1&limit=300&overlays=ema:20,ema:50,rsi:14': () =>
        json(candles('XAUUSD')),
    });
    const user = userEvent.setup();
    renderShell('/charts?decision=d1&tf=H1');
    expect(await screen.findByText('Signal XAUUSD SELL (H1)')).toBeInTheDocument();
    await waitFor(() => {
      expect(lastModel().priceLines.map((p) => p.title)).toContain('Fibonacci retracement: fib_61.8');
    });
    expect(lastModel().priceLines.map((p) => p.title)).toEqual(
      expect.arrayContaining(['Signal entry', 'SL', 'TP']),
    );
    const titles = () => lastModel().priceLines.map((p) => p.title);
    expect(titles().some((x) => x.startsWith('Donchian'))).toBe(false); // conflicting: not drawn at first
    await user.click(screen.getByText('Against the signal (1)'));
    await user.click(screen.getByRole('checkbox', { name: /Donchian breakout/ }));
    await waitFor(() => {
      expect(titles()).toContain('Donchian breakout: channel_20');
    });
    expect(titles()).not.toContain('Donchian breakout: invalidation');
    await user.click(screen.getByRole('checkbox', { name: 'Show invalidation levels' }));
    await waitFor(() => {
      expect(titles()).toContain('Donchian breakout: invalidation');
    });
    await user.click(screen.getByRole('checkbox', { name: /Fibonacci retracement/ }));
    await waitFor(() => {
      expect(titles()).not.toContain('Fibonacci retracement: fib_61.8');
    });
    await user.click(screen.getByRole('button', { name: 'Key items only' }));
    await waitFor(() => {
      expect(titles()).toContain('Fibonacci retracement: fib_61.8');
    });
    expect(titles().some((x) => x.startsWith('Donchian'))).toBe(false);
    await user.click(screen.getByRole('button', { name: 'Hide signal' }));
    expect(screen.queryByText('Signal XAUUSD SELL (H1)')).not.toBeInTheDocument();
  });

  it('draws the bot open broker positions like paper ones (TAA-1211)', async () => {
    const bot = {
      ticket: 77,
      symbol: 'EURUSD',
      side: 'BUY',
      volume: 0.1,
      price_open: 1.1005,
      price_current: 1.101,
      sl: 1.099,
      tp: 1.104,
      sl_initial: 1.099,
      profit: 5,
      swap: 0,
      opened_at: iso(T0),
      magic: 7310002,
      strategy: null,
      risk_to_stop: 15,
    };
    setup({
      'GET /engines/e1/status': () =>
        json(
          status('e1', {
            heartbeat: heartbeat({ mode: 'DEMO', account: { ...ACCOUNT, bot_positions: [bot] } }),
          }),
        ),
    });
    renderShell('/charts');
    await waitFor(() => {
      expect(lastModel().priceLines.map((p) => p.title)).toEqual(
        expect.arrayContaining(['#77 BUY', 'SL #77']),
      );
    });
  });

  it('says when a symbol has no candles yet', async () => {
    setup({
      'GET /engines/e1/candles?symbol=EURUSD&timeframe=M15&limit=300&overlays=ema:20,ema:50,rsi:14&zones=true':
        () => apiError(404, 'candles_not_found'),
    });
    renderShell('/charts');
    expect(await screen.findByText('No candles for this symbol yet.')).toBeInTheDocument();
  });

  it('redraws markers when a position changes on the stream', async () => {
    const api = setup();
    const { sources } = renderShell('/charts');
    await waitFor(() => {
      expect(drawn.models.length).toBeGreaterThan(0);
    });
    const candleCalls = () => api.calls.filter((c) => c.path.startsWith('/engines/e1/candles')).length;
    const before = candleCalls();
    act(() => {
      sources.last().emit('ready', { cursor: 1, resumed: true });
      sources.last().emit('positions', streamEvent(2, 'paper_position', {}));
    });
    await waitFor(() => {
      expect(candleCalls()).toBe(before + 1);
    });
  });

  it('follows the theme and cleans up on leaving', async () => {
    setup();
    const user = userEvent.setup();
    const { router } = renderShell('/charts');
    await waitFor(() => {
      expect(drawn.models.length).toBeGreaterThan(0);
    });
    await user.selectOptions(screen.getByRole('combobox', { name: 'Theme' }), 'dark');
    await waitFor(() => {
      expect(drawn.themes.at(-1)).toBe(true);
    });
    await act(async () => {
      await router.navigate('/settings');
    });
    expect(drawn.destroyed).toBe(1);
    await user.selectOptions(screen.getByRole('combobox', { name: 'Theme' }), 'light');
  });
});
