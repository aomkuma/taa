"""Single-use TOTP verification on the engine (PLAN §A13 "Commands", §A20; TAA-704).

Remote POSITION_CLOSE and FLATTEN_ALL need a 6-digit RFC 6238 code from the owner's authenticator, checked
here against ``CONTROL_TOTP_SECRET``, a secret the cloud never holds. A code is accepted within ±1 time step
(30 s) of the engine clock and **only once**: the matched time step is remembered, so a code captured in
transit cannot be replayed for another command. Used steps can be preloaded after a restart (the engine keeps
them in its command log).
"""

from __future__ import annotations

import hmac
from collections.abc import Iterable

import pyotp

from app.core.clock import Clock
from app.core.errors import ConfigError


class SingleUseTotp:
    def __init__(
        self,
        secret: str,
        clock: Clock,
        *,
        valid_window: int = 1,
        used_steps: Iterable[int] = (),
    ) -> None:
        try:
            self._totp = pyotp.TOTP(secret)
            self._totp.at(0)
        except (ValueError, TypeError) as exc:  # binascii.Error is a ValueError
            raise ConfigError("CONTROL_TOTP_SECRET is not a valid base32 secret") from exc
        self.clock = clock
        self.valid_window = valid_window
        self.interval = self._totp.interval
        self._used: set[int] = set(used_steps)

    def step(self) -> int:
        return int(self.clock.now_utc().timestamp()) // self.interval

    def match(self, code: str) -> int | None:
        """The time step *code* belongs to (within the window), or None. Does not consume it."""
        code = code.strip()
        if len(code) != self._totp.digits or not code.isdigit():
            return None
        now = self.step()
        for step in range(now - self.valid_window, now + self.valid_window + 1):
            if hmac.compare_digest(self._totp.at(step * self.interval), code):
                return step
        return None

    def verify(self, code: str | None) -> int | None:
        """Consume a valid, unused code: returns its time step, or None (invalid, expired or reused)."""
        if not code:
            return None
        step = self.match(code)
        if step is None or step in self._used:
            return None
        self._used.add(step)
        self._used = {s for s in self._used if s >= self.step() - 10}  # older steps can never match again
        return step
