"""Detector registry, run plans and the evidence engine (PLAN §A29, selective computation per §A30).

- The registry validates the detector catalog once: unique ids, known prerequisites, no dependency cycles.
- :meth:`DetectorRegistry.plan` turns a set of *requested* detectors into a run plan: the requested ones plus
  every prerequisite (transitively), in dependency order. Only requested detectors produce output;
  prerequisites run only to feed them. Anything else is never executed.
- :class:`EvidenceEngine` runs a plan on a context, validates every record, keeps per-detector call counters
  and timings, and turns the output into an immutable :class:`EvidenceSnapshot`.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from pydantic import ValidationError

from app.config import EvidenceConfig
from app.core.errors import ConfigError, EvidenceError
from app.core.ids import stable_hash
from app.evidence.framework import (
    Detector,
    DetectorParams,
    Evidence,
    EvidenceContext,
    EvidenceSnapshot,
    activate,
)


@dataclass(frozen=True)
class RunPlan:
    order: tuple[str, ...]  # every detector to execute, prerequisites first
    outputs: frozenset[str]  # detectors whose evidence is reported
    params: Mapping[str, DetectorParams]

    @property
    def params_digest(self) -> str:
        payload = {d: self.params[d].model_dump(mode="json") for d in self.order}
        return stable_hash(json.dumps(payload, sort_keys=True, separators=(",", ":")))


class DetectorRegistry:
    def __init__(self, detectors: Iterable[Detector]) -> None:
        self._detectors: dict[str, Detector] = {}
        for det in detectors:
            if det.id in self._detectors:
                raise EvidenceError(f"duplicate detector id {det.id!r}")
            self._detectors[det.id] = det
        for det in self._detectors.values():
            unknown = [d for d in det.depends_on if d not in self._detectors]
            if unknown:
                raise EvidenceError(f"{det.id} depends on unknown detectors {unknown}")
        self._topo = self._topological_order()

    @property
    def ids(self) -> list[str]:
        return list(self._topo)

    def get(self, detector_id: str) -> Detector:
        try:
            return self._detectors[detector_id]
        except KeyError:
            raise ConfigError(f"unknown detector {detector_id!r}") from None

    def _topological_order(self) -> tuple[str, ...]:
        order: list[str] = []
        state: dict[str, int] = {}  # 1 = visiting, 2 = done

        def visit(det_id: str, path: tuple[str, ...]) -> None:
            if state.get(det_id) == 2:
                return
            if state.get(det_id) == 1:
                raise EvidenceError(f"detector dependency cycle: {' -> '.join((*path, det_id))}")
            state[det_id] = 1
            for dep in self._detectors[det_id].depends_on:
                visit(dep, (*path, det_id))
            state[det_id] = 2
            order.append(det_id)

        for det_id in sorted(self._detectors):
            visit(det_id, ())
        return tuple(order)

    def default_params(self, detector_id: str) -> DetectorParams:
        return self.get(detector_id).Params()

    def parse_params(self, detector_id: str, raw: Mapping[str, object]) -> DetectorParams:
        det = self.get(detector_id)
        try:
            return det.Params.model_validate(dict(raw))
        except ValidationError as exc:
            raise ConfigError(f"invalid params for detector {detector_id}: {exc}") from exc

    def plan(self, requested: Iterable[str], params: Mapping[str, DetectorParams] | None = None) -> RunPlan:
        wanted = set(requested)
        for det_id in wanted:
            self.get(det_id)
        needed: set[str] = set()
        stack = list(wanted)
        while stack:
            det_id = stack.pop()
            if det_id not in needed:
                needed.add(det_id)
                stack.extend(self._detectors[det_id].depends_on)
        given = dict(params or {})
        resolved = {d: given.get(d) or self.default_params(d) for d in needed}
        order = tuple(d for d in self._topo if d in needed)
        return RunPlan(order, frozenset(wanted), MappingProxyType(resolved))

    def plan_from_config(self, config: EvidenceConfig, *, only: Iterable[str] | None = None) -> RunPlan:
        """Enabled detectors from ``config.yaml`` → ``evidence:``.

        *only* (the union of what active users selected) narrows the set further. Unknown ids and invalid
        params are configuration errors.
        """
        for det_id in config.detectors:
            self.get(det_id)
        params = {d: self.parse_params(d, s.params) for d, s in config.detectors.items()}
        enabled = {
            d
            for d in self._detectors
            if (
                config.detectors[d].enabled
                if d in config.detectors and config.detectors[d].enabled is not None
                else config.default_enabled
            )
        }
        if only is not None:
            enabled &= set(only)
        return self.plan(enabled, params)


@dataclass
class DetectorStats:
    calls: int = 0
    seconds: float = 0.0
    records: int = 0


@dataclass
class EvidenceEngine:
    registry: DetectorRegistry
    plan: RunPlan
    stats: dict[str, DetectorStats] = field(default_factory=dict)

    def scan(self, ctx: EvidenceContext) -> dict[str, list[Evidence]]:
        """Run every detector of the plan; return the evidence of the requested (output) detectors."""
        out: dict[str, list[Evidence]] = {}
        for det_id in self.plan.order:
            det = self.registry.get(det_id)
            started = time.perf_counter()
            records = det.scan(ctx, self.plan.params[det_id])
            elapsed = time.perf_counter() - started
            self._check(det, ctx, records)
            stat = self.stats.setdefault(det_id, DetectorStats())
            stat.calls += 1
            stat.seconds += elapsed
            stat.records += len(records)
            ctx.store_results(det_id, records)
            if det_id in self.plan.outputs:
                out[det_id] = records
        return out

    def evaluate(self, ctx: EvidenceContext) -> EvidenceSnapshot:
        """Evidence active at the last bar of *ctx*, as an immutable snapshot."""
        found = self.scan(ctx)
        max_age = {d: self.plan.params[d].max_age_bars for d in found}
        items = activate(ctx, [e for records in found.values() for e in records], max_age)
        return EvidenceSnapshot(
            symbol=ctx.symbol,
            timeframe=ctx.timeframe,
            as_of=ctx.as_of,
            items=tuple(items),
            detectors=tuple((d, self.registry.get(d).version) for d in sorted(found)),
            params_digest=self.plan.params_digest,
        )

    @staticmethod
    def _check(det: Detector, ctx: EvidenceContext, records: list[Evidence]) -> None:
        for ev in records:
            if ev.detector_id != det.id or ev.family is not det.family or ev.tier is not det.tier:
                raise EvidenceError(f"{det.id} produced a record labelled {ev.detector_id}/{ev.family}")
            if ev.symbol != ctx.symbol or ev.timeframe is not ctx.timeframe:
                raise EvidenceError(f"{det.id} produced a record for another symbol/timeframe")
            ctx.pos_of(ev.detected_at)  # raises if not a bar of this frame (e.g. a future time)
