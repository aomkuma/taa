"""Providers for replays of past days (PLAN §A37, TAA-1807).

- :class:`ReplayProvider` stores every answer by the hash of its input (model, effort, system prompt, content,
  answer schema): a replay asks only what it has not asked before, so it is repeatable and its cost bounded.
  A miss goes to the inner provider (or answers SKIPPED without one).
- :class:`ClaudeCLIProvider` answers through the Claude Code CLI in print mode (owner 2026-10-24: a Sonnet
  subagent instead of paid API calls). Every call is a fresh session with no tools, no MCP servers, no
  settings, no CLAUDE.md and no memory, run in an empty folder, so the model sees only the prompt - it cannot
  read the stored prices. The CLI's reported cost (list prices) is kept, so the watcher's daily cap acts as
  live.
- :class:`CodexCLIProvider` answers through the Codex CLI (``codex exec``; owner 2026-10-26: "work with Codex
  when running tests - the AI now on Sonnet to use GPT-6-Luna"): the same empty folder, a read-only sandbox,
  no session kept, the answer held to the schema in OpenAI's strict form; an answer whose events show any
  command, file read or tool call is refused (it could have read the stored prices).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import subprocess  # nosec B404 - the Claude CLI, a fixed executable with an argument list (no shell)
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from app.ai.providers import AIProvider, Answer, assess_with, cost_usd
from app.ai.schema import Assessment, AssessmentInput, Status
from app.core.clock import Clock

log = logging.getLogger(__name__)

CLI_TIMEOUT_SECONDS = 600.0
CLI_RETRY_SECONDS = 10.0  # one retry after a fast CLI error (two such on the first replayed day, 2026-07-06)


def input_hash(
    system: str, content: str, output_format: type[BaseModel], model: str | None, effort: str | None
) -> str:
    """The answer's key: everything the model is given (the call's ``key`` label is not part of it)."""
    blob = json.dumps(
        {
            "model": model,
            "effort": effort,
            "schema": output_format.model_json_schema(),  # the answer's fields too
            "system": system,
            "content": content,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def live_cost(model: str | None, system: str, content: str, tokens_in: int, tokens_out: int) -> float:
    """What the call would cost live through the API (the system prompt a warm cache read, the rest fresh
    input): the CLI's input tokens split by the two parts' lengths. The CLI bills each fresh session's whole
    prompt as a cache write, about twice the live price, which would trip the watcher's daily cap early."""
    total = len(system) + len(content)
    cached = round(tokens_in * len(system) / total) if total else 0
    return cost_usd(model, tokens_in - cached, tokens_out, 0, cached)


class ReplayProvider:
    """Answers from ``answers/<hash>.json``; a miss asks ``inner`` and stores an OK answer. ``spend`` is what
    each answer costs the watcher's daily cap: ``stored`` the answerer's figure, ``api`` the live API price
    (:func:`live_cost`), ``none`` nothing (live answers through the CLI on the owner's plan first, owner
    2026-10-24: the cap counts only paid API calls). The stored row always keeps the answerer's own."""

    name = "replay"

    def __init__(
        self,
        answers: Path,
        clock: Clock,
        inner: AIProvider | None = None,
        *,
        spend: Literal["stored", "api", "none"] = "stored",
    ) -> None:
        self.answers = answers
        self.clock = clock
        self.inner = inner
        self.spend = spend
        self.hits = 0
        self.misses = 0

    def assess(self, request: AssessmentInput) -> Assessment:
        return Assessment(
            Status.SKIPPED, request.signal_key, created_at=self.clock.now_utc(), detail="replay"
        )

    def ask(
        self,
        key: str,
        system: str,
        content: str,
        output_format: type[BaseModel],
        *,
        model: str | None = None,
        effort: str | None = None,
        cache_system: bool = False,
    ) -> Answer:
        h = input_hash(system, content, output_format, model, effort)
        path = self.answers / f"{h}.json"
        ans = self._answer(h, path, key, system, content, output_format, model, effort, cache_system)
        if self.spend == "stored" or ans.status is not Status.OK:
            return ans
        if self.spend == "none":
            return dataclasses.replace(ans, cost_usd=0.0)
        tokens_in = ans.input_tokens + ans.cache_write_tokens + ans.cache_read_tokens
        return dataclasses.replace(
            ans, cost_usd=live_cost(ans.model, system, content, tokens_in, ans.output_tokens)
        )

    def _answer(
        self,
        h: str,
        path: Path,
        key: str,
        system: str,
        content: str,
        output_format: type[BaseModel],
        model: str | None,
        effort: str | None,
        cache_system: bool,
    ) -> Answer:
        if path.exists():
            self.hits += 1
            row = json.loads(path.read_text(encoding="utf-8"))
            return Answer(
                Status(row["status"]),
                parsed=output_format.model_validate(row["parsed"]) if row.get("parsed") is not None else None,
                model=row.get("model"),
                input_tokens=int(row.get("input_tokens", 0)),
                output_tokens=int(row.get("output_tokens", 0)),
                cost_usd=float(row.get("cost_usd", 0.0)),
                latency_ms=row.get("latency_ms"),
                detail=f"replayed {h[:12]}",
                created_at=self.clock.now_utc(),
                cache_write_tokens=int(row.get("cache_write_tokens", 0)),
                cache_read_tokens=int(row.get("cache_read_tokens", 0)),
            )
        self.misses += 1
        if self.inner is None:
            return Answer(
                Status.SKIPPED, created_at=self.clock.now_utc(), detail=f"no stored answer {h[:12]}"
            )
        ans = self.inner.ask(
            key, system, content, output_format, model=model, effort=effort, cache_system=cache_system
        )
        if ans.status is Status.OK and ans.parsed is not None:  # a failure is asked again next time
            self.answers.mkdir(parents=True, exist_ok=True)
            row = {
                "key": key,
                "status": ans.status.value,
                "parsed": ans.parsed.model_dump(mode="json"),
                "model": ans.model,
                "input_tokens": ans.input_tokens,
                "output_tokens": ans.output_tokens,
                "cache_write_tokens": ans.cache_write_tokens,
                "cache_read_tokens": ans.cache_read_tokens,
                "cost_usd": ans.cost_usd,
                "latency_ms": ans.latency_ms,
            }
            path.write_text(json.dumps(row, indent=1, ensure_ascii=False), encoding="utf-8")
        return ans


class ClaudeCLIProvider:
    """The Claude Code CLI (``claude -p``) as the answerer: one fresh, tool-less session per call."""

    name = "claude-cli"

    def __init__(
        self, exe: Path, clock: Clock, *, model: str = "claude-sonnet-5-5", effort: str = "medium"
    ) -> None:
        self.exe = exe
        self.clock = clock
        self.model = model
        self.effort = effort

    def assess(self, request: AssessmentInput) -> Assessment:
        return Assessment(Status.SKIPPED, request.signal_key, created_at=self.clock.now_utc(), detail="cli")

    def command(self, system_file: Path, schema: dict[str, Any], model: str, effort: str) -> list[str]:
        return [
            str(self.exe), "-p", "--model", model, "--effort", effort,
            "--tools", "", "--strict-mcp-config", "--setting-sources", "", "--no-session-persistence",
            "--exclude-dynamic-system-prompt-sections", "--system-prompt-file", str(system_file),
            "--output-format", "json", "--json-schema", json.dumps(schema),
        ]  # fmt: skip

    def ask(
        self,
        key: str,
        system: str,
        content: str,
        output_format: type[BaseModel],
        *,
        model: str | None = None,
        effort: str | None = None,
        cache_system: bool = False,
    ) -> Answer:
        used, level = model or self.model, effort or self.effort
        ans = self._once(system, content, output_format, used, level)
        if ans.status is Status.ERROR:
            log.warning("Claude CLI error (%s); one retry in %.0f s", ans.detail[:200], CLI_RETRY_SECONDS)
            time.sleep(CLI_RETRY_SECONDS)
            ans = self._once(system, content, output_format, used, level)
        return ans

    def _once(
        self, system: str, content: str, output_format: type[BaseModel], used: str, level: str
    ) -> Answer:
        now: datetime = self.clock.now_utc()
        started = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix="taa-ai-") as tmp:  # an empty folder: nothing to read
            system_file = Path(tmp) / "system.txt"
            system_file.write_text(system, encoding="utf-8")
            try:
                run = subprocess.run(  # noqa: S603  # nosec B603 - a fixed executable, an argument list, no shell
                    self.command(system_file, output_format.model_json_schema(), used, level),
                    input=content, capture_output=True, text=True, encoding="utf-8", cwd=tmp,
                    timeout=CLI_TIMEOUT_SECONDS, check=False,
                )  # fmt: skip
            except subprocess.TimeoutExpired:
                return Answer(Status.TIMEOUT, model=used, created_at=now, detail="the CLI timed out")
            except OSError as exc:
                return Answer(
                    Status.ERROR, model=used, created_at=now, detail=f"the CLI did not start: {exc}"
                )
        latency = round((time.perf_counter() - started) * 1000, 1)
        return parse_cli(run.stdout, output_format, used, now, latency, run.stderr)


class CodexCLIProvider:
    """The Codex CLI (``codex exec``) as the answerer: one fresh session per call in an empty folder."""

    name = "codex-cli"

    def __init__(self, exe: Path, clock: Clock, *, model: str = "gpt-6-luna", effort: str = "medium") -> None:
        self.exe = exe
        self.clock = clock
        self.model = model
        self.effort = effort

    def assess(self, request: AssessmentInput) -> Assessment:
        return assess_with(self, request)  # the entry review too (AI_MODE veto / advisory)

    def command(self, folder: Path, schema_file: Path, out_file: Path, model: str, effort: str) -> list[str]:
        return [
            str(self.exe), "exec", "-m", model, "-c", f'model_reasoning_effort="{effort}"',
            "-s", "read-only", "--ephemeral", "--skip-git-repo-check", "-C", str(folder),
            "--output-schema", str(schema_file), "-o", str(out_file), "--json", "-",
        ]  # fmt: skip

    def ask(
        self,
        key: str,
        system: str,
        content: str,
        output_format: type[BaseModel],
        *,
        model: str | None = None,
        effort: str | None = None,
        cache_system: bool = False,
    ) -> Answer:
        used, level = self.model, effort or self.effort  # the caller's model names a Claude one: Codex's own
        ans = self._once(system, content, output_format, used, level)
        if ans.status is Status.ERROR:
            log.warning("Codex CLI error (%s); one retry in %.0f s", ans.detail[:200], CLI_RETRY_SECONDS)
            time.sleep(CLI_RETRY_SECONDS)
            ans = self._once(system, content, output_format, used, level)
        return ans

    def _once(
        self, system: str, content: str, output_format: type[BaseModel], used: str, level: str
    ) -> Answer:
        now: datetime = self.clock.now_utc()
        started = time.perf_counter()
        schema = output_format.model_json_schema()
        with tempfile.TemporaryDirectory(prefix="taa-ai-") as tmp:
            folder = Path(tmp) / "empty"  # nothing to read
            folder.mkdir()
            schema_file, out_file = Path(tmp) / "schema.json", Path(tmp) / "answer.json"
            schema_file.write_text(json.dumps(strict_schema(schema)), encoding="utf-8")
            prompt = f"{CODEX_RULES}\n\n# SYSTEM\n{system}\n\n# INPUT\n{content}"
            try:
                run = subprocess.run(  # noqa: S603  # nosec B603 - a fixed executable, an argument list, no shell
                    self.command(folder, schema_file, out_file, used, level),
                    input=prompt, capture_output=True, text=True, encoding="utf-8", cwd=folder,
                    timeout=CLI_TIMEOUT_SECONDS, check=False,
                )  # fmt: skip
            except subprocess.TimeoutExpired:
                return Answer(Status.TIMEOUT, model=used, created_at=now, detail="the CLI timed out")
            except OSError as exc:
                return Answer(
                    Status.ERROR, model=used, created_at=now, detail=f"the CLI did not start: {exc}"
                )
            answer = out_file.read_text(encoding="utf-8") if out_file.exists() else ""
        latency = round((time.perf_counter() - started) * 1000, 1)
        return parse_codex(run.stdout, answer, schema, output_format, used, now, latency, run.stderr)


def find_codex() -> Path | None:
    """The newest Codex CLI of the VS Code ChatGPT extension (where the owner installed Codex), or None."""
    found = sorted(Path.home().glob(".vscode/extensions/openai.chatgpt-*/bin/windows-x86_64/codex.exe"))
    return found[-1] if found else None


CODEX_RULES = (
    "Answer from the text below only. Do not run any command, read any file or use any tool: the answer is "
    "refused if you do. Reply with the JSON the schema asks for; a field you leave empty is null."
)
TOOL_EVENTS = ("command", "exec", "file", "tool", "patch", "search", "mcp")  # item types that read or act


def strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """``schema`` in OpenAI's strict form: every object closed (additionalProperties false) with every
    property required, a property that was optional made nullable, and the keyword strict mode refuses
    (default) dropped. :func:`unstrict` takes those nulls out again so the model's own defaults apply."""

    def walk(node: Any) -> Any:
        if isinstance(node, list):
            return [walk(x) for x in node]
        if not isinstance(node, dict):
            return node
        out = {k: walk(v) for k, v in node.items() if k != "default"}
        if out.get("type") == "object" and "properties" in out:
            required = set(node.get("required", []))
            props = {}
            for name, sub in out["properties"].items():
                keep = name in required or allows_null(sub)
                props[name] = sub if keep else {"anyOf": [sub, {"type": "null"}]}
            out["properties"], out["required"], out["additionalProperties"] = props, list(props), False
        return out

    result: dict[str, Any] = walk(schema)
    return result


def allows_null(sub: dict[str, Any]) -> bool:
    return sub.get("type") == "null" or any(x.get("type") == "null" for x in sub.get("anyOf", []))


def unstrict(value: Any, schema: dict[str, Any], defs: dict[str, Any]) -> Any:
    """``value`` without the nulls strict mode put in optional fields that do not allow null themselves."""
    if "$ref" in schema:
        schema = defs.get(schema["$ref"].split("/")[-1], {})
    if isinstance(value, dict) and "properties" in schema:
        props = schema["properties"]
        return {
            k: unstrict(v, props.get(k, {}), defs)
            for k, v in value.items()
            if not (v is None and k in props and not allows_null(props[k]))
        }
    if isinstance(value, list) and "items" in schema:
        return [unstrict(v, schema["items"], defs) for v in value]
    return value


def parse_codex(
    stdout: str,
    answer: str,
    schema: dict[str, Any],
    output_format: type[BaseModel],
    model: str,
    now: datetime,
    latency: float,
    stderr: str = "",
) -> Answer:
    """The Codex CLI's events (``--json``) and last message as an :class:`Answer`: refused when an event shows
    a command, file read or tool call; else the message validated against the schema. Codex runs on the
    owner's plan: no cost is counted."""
    usage: dict[str, Any] = {}
    for line in stdout.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = ev.get("item") or {}
        kind = str(item.get("type") or item.get("item_type") or "")
        if any(word in kind for word in TOOL_EVENTS):
            detail = f"the answerer used a tool ({kind}): refused"
            return Answer(Status.ERROR, model=model, created_at=now, latency_ms=latency, detail=detail)
        if ev.get("type") == "turn.completed":
            usage = ev.get("usage") or {}
        if ev.get("type") in ("turn.failed", "error"):
            detail = str((ev.get("error") or {}).get("message") or ev.get("message") or "")[:500]
            return Answer(Status.ERROR, model=model, created_at=now, latency_ms=latency, detail=detail)
    spend: dict[str, Any] = {
        "model": model,
        "input_tokens": int(usage.get("input_tokens", 0)),
        "output_tokens": int(usage.get("output_tokens", 0)),
        "cache_read_tokens": int(usage.get("cached_input_tokens", 0)),
        "latency_ms": latency,
        "created_at": now,
    }
    try:
        raw = json.loads(answer)
    except json.JSONDecodeError:
        return Answer(Status.ERROR, detail=(answer or stderr.strip()[-300:] or "no answer")[:500], **spend)
    try:
        parsed = output_format.model_validate(unstrict(raw, schema, schema.get("$defs", {})))
    except ValidationError as exc:
        return Answer(Status.INVALID, detail=str(exc)[:500], **spend)
    return Answer(Status.OK, parsed=parsed, **spend)


def parse_cli(
    stdout: str, output_format: type[BaseModel], model: str, now: datetime, latency: float, stderr: str = ""
) -> Answer:
    """The CLI's JSON result as an :class:`Answer`: the structured output validated against the schema, the
    model's tokens and list-price cost."""
    try:
        out = json.loads(stdout)
    except json.JSONDecodeError:
        return Answer(
            Status.ERROR, model=model, created_at=now, latency_ms=latency, detail=(stderr or stdout)[:500]
        )
    usage = (out.get("modelUsage") or {}).get(model) or {}
    spend: dict[str, Any] = {
        "model": model,
        "input_tokens": int(usage.get("inputTokens", 0)),
        "output_tokens": int(usage.get("outputTokens", 0)),
        "cache_write_tokens": int(usage.get("cacheCreationInputTokens", 0)),
        "cache_read_tokens": int(usage.get("cacheReadInputTokens", 0)),
        "cost_usd": round(float(usage.get("costUSD", 0.0)), 6),
        "latency_ms": latency,
        "created_at": now,
    }
    if out.get("is_error") or out.get("structured_output") is None:
        why = [str(out.get(k)) for k in ("result", "terminal_reason", "api_error_status") if out.get(k)]
        return Answer(
            Status.ERROR,
            detail="; ".join(why + [stderr.strip()[-200:]] * bool(stderr.strip()))[:500],
            **spend,
        )
    try:
        parsed = output_format.model_validate(out["structured_output"])
    except ValidationError as exc:
        return Answer(Status.INVALID, detail=str(exc)[:500], **spend)
    return Answer(Status.OK, parsed=parsed, **spend)
