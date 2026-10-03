"""Exception hierarchy. Every error raised by TAA code derives from :class:`TaaError`."""

from __future__ import annotations


class TaaError(Exception):
    """Base class for all TAA errors."""


class ConfigError(TaaError):
    """Invalid or missing configuration. The process must refuse to start."""


class SecretError(ConfigError):
    """A secret could not be resolved (missing env var, keyring entry, ...)."""


class SafetyViolation(TaaError):
    """An action was attempted that a safety rule forbids (e.g. order in PAPER mode)."""


class BrokerError(TaaError):
    """Generic broker/terminal failure."""


class BrokerUnavailable(BrokerError):
    """The terminal is not initialized, not connected or not authorized."""


class AccountVerificationError(BrokerError):
    """The connected account does not match configuration or mode requirements."""


class SymbolUnavailable(BrokerError):
    """A symbol does not exist, cannot be selected, or has invalid specifications."""


class DataQualityError(TaaError):
    """Market data failed validation (stale, gaps, inconsistent OHLC, ...)."""


class InsufficientDataError(DataQualityError):
    """Not enough bars for indicator warm-up."""


class StorageError(TaaError):
    """Database or file-storage failure."""


class AuditChainError(StorageError):
    """The audit hash chain is broken (possible tampering or corruption)."""


class EvidenceError(TaaError):
    """A detector produced an invalid evidence record or the detector setup is inconsistent."""
