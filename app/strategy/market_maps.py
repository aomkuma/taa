"""The higher-timeframe market map at a decision time: live engine, scanner and replay (TAA-L809).

:class:`MapBook` turns closed candles of the context timeframes (``timeframes.context``) into a
:class:`~app.indicators.market_map.MarketMap` at an entry bar's close. One code path serves live and history:

- the per-bar states (:func:`~app.indicators.market_map.state_frame`) are computed once per candle frame
  (live: once per new context bar; history: once per symbol) and cached by the frame's first/last close time;
- the map of a context bar is computed once and cached by its position, so the many entry bars inside one H4
  bar share it.

Only bars closed at or before the decision time are used (``close_time <= t``). A context timeframe without
enough bars is left out of the map instead of guessed.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime

import pandas as pd

from app.config import AppConfig
from app.core.clock import ensure_utc
from app.core.enums import Timeframe
from app.indicators.market_map import MapParams, MarketMap, TimeframeMap, state_frame, timeframe_map

log = logging.getLogger(__name__)

MIN_BARS = 60  # fewer closed context bars than this: the timeframe is left out (warm-up)


def map_params(config: AppConfig, timeframe: Timeframe | None = None) -> MapParams:
    """The map parameters, with ``context_map.by_timeframe`` applied for *timeframe* (if given)."""
    c, reg = config.context_map, config.regime
    base = _base_params(config)
    o = None if timeframe is None else c.by_timeframe.get(timeframe)
    if o is None:
        return base
    return replace(
        base,
        er_bars=base.er_bars if o.er_bars is None else o.er_bars,
        er_trend=base.er_trend if o.er_trend is None else o.er_trend,
        er_range=base.er_range if o.er_range is None else o.er_range,
        trend_adx=reg.trend_adx if o.trend_adx is None else o.trend_adx,
        range_adx=reg.range_adx if o.range_adx is None else o.range_adx,
    )


def _base_params(config: AppConfig) -> MapParams:
    c, ind, reg = config.context_map, config.indicators, config.regime
    return MapParams(
        ema_mid=ind.ema_mid,
        ema_slow=ind.ema_slow,
        adx_period=ind.adx_period,
        atr_period=ind.atr_period,
        trend_adx=reg.trend_adx,
        range_adx=reg.range_adx,
        er_bars=c.er_bars,
        er_trend=c.er_trend,
        er_range=c.er_range,
        switch_bars=c.switch_bars,
        swing_k=ind.swing_k,
        range_bars=c.range_bars,
        compression_pct=c.compression_pct,
        pct_lookback=ind.atr_percentile_lookback,
        bb_period=ind.bb_period,
        zone_lookback_bars=c.zone_lookback_bars,
        zone_tolerance_atr=c.zone_tolerance_atr,
        min_touches=c.min_touches,
        displacement_atr=c.displacement_atr,
        max_tests=c.max_tests,
        max_zones=c.max_zones,
        zone_near_atr=c.zone_near_atr,
    )


def candle_frame(df: pd.DataFrame) -> pd.DataFrame:
    """``CANDLE_COLUMNS`` rows → open/high/low/close indexed by UTC close time, oldest first."""
    index = pd.DatetimeIndex(pd.to_datetime(df["close_time"], utc=True))
    out = pd.DataFrame(
        {c: df[c].to_numpy(dtype=float) for c in ("open", "high", "low", "close")}, index=index
    )
    return out.sort_index()


class MapBook:
    def __init__(
        self,
        params: MapParams,
        timeframes: list[Timeframe],
        by_timeframe: dict[Timeframe, MapParams] | None = None,
    ) -> None:
        self.params = params
        self.timeframes = list(timeframes)
        self.by_timeframe = dict(by_timeframe or {})
        self._states: dict[tuple[str, Timeframe], tuple[tuple[object, object, int], pd.DataFrame]] = {}
        self._maps: dict[tuple[str, Timeframe, object], TimeframeMap] = {}

    @classmethod
    def from_config(cls, config: AppConfig) -> MapBook | None:
        tfs = config.timeframes.context
        if not tfs:
            return None
        return cls(map_params(config), tfs, {tf: map_params(config, tf) for tf in tfs})

    def at(self, symbol: str, candles: Mapping[Timeframe, pd.DataFrame], t: datetime) -> MarketMap | None:
        """The map at *t* from *candles* (per context timeframe, :func:`candle_frame` form); None if empty."""
        at = pd.Timestamp(ensure_utc(t))
        frames: dict[str, TimeframeMap] = {}
        for tf in self.timeframes:
            frame = candles.get(tf)
            if frame is None or frame.empty:
                continue
            pos = int(frame.index.searchsorted(at, side="right")) - 1
            if pos + 1 < MIN_BARS:
                continue
            states = self._states_of(symbol, tf, frame)
            key = (symbol, tf, frame.index[pos])
            m = self._maps.get(key)
            if m is None:
                m = timeframe_map(tf.value, frame, states, pos, self._params(tf))
                self._maps[key] = m
            frames[tf.value] = m
        if not frames:
            return None
        return MarketMap(frames, near_atr=self.params.zone_near_atr, room_cap_r=self.params.room_cap_r)

    def _params(self, tf: Timeframe) -> MapParams:
        return self.by_timeframe.get(tf, self.params)

    def _states_of(self, symbol: str, tf: Timeframe, frame: pd.DataFrame) -> pd.DataFrame:
        sig = (frame.index[0], frame.index[-1], len(frame))
        cached = self._states.get((symbol, tf))
        if cached is not None and cached[0] == sig:
            return cached[1]
        states = state_frame(frame, self._params(tf))
        self._states[(symbol, tf)] = (sig, states)
        stale = [k for k in self._maps if k[0] == symbol and k[1] is tf and k[2] < frame.index[0]]
        for k in stale:
            del self._maps[k]
        return states
