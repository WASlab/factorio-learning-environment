"""Program template store: agent-authored reusable programs.

Program templates are macros over the canonical semantic-motor tools.  A
template is a short Python program body with declared ``{{name}}`` parameters.
It grants no new powers: the body is expanded with concrete argument literals
and then validated by the same ``validate_program`` policy as any hand-written
program before it is executed and hashed.  Material requirements, forbidden
actions, and replay accounting therefore apply unchanged.

Scoping mirrors :mod:`fle.envd.blueprints`:

- ``scope=None``      -> ephemeral, dies with the lease (benchmark default;
                         evaluation never sees cross-episode state).
- ``scope="lineage"`` -> durable SQLite rows shared by every rollout in a
                         training generation; fresh generations start clean.

Parameters must declare a default so a saved template is always runnable and
can be policy-validated at save time.  Arguments are JSON values (strings,
numbers, booleans, null, arrays, objects); enum symbols such as ``Prototype``
or ``Direction`` cannot cross the JSON boundary, so template bodies that need
them reference the symbols directly.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TEMPLATE_STORE_VERSION = "program-template-store-v1"
MAX_TEMPLATE_BYTES = 64 * 1024
DEFAULT_MAX_PER_SCOPE = 64
_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_PARAMETER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,31}$")
_PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS program_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    parameters TEXT NOT NULL DEFAULT '[]',
    code TEXT NOT NULL,
    body_sha256 TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    created_tick INTEGER,
    times_run INTEGER NOT NULL DEFAULT 0,
    last_used_tick INTEGER,
    last_used_lease TEXT,
    UNIQUE(scope, name)
);
CREATE INDEX IF NOT EXISTS idx_program_templates_scope
    ON program_templates(scope);
"""


class TemplateError(Exception):
    """Base class for template store failures surfaced to the agent."""


class TemplateQuotaExceeded(TemplateError):
    pass


class TemplateNotFound(TemplateError):
    pass


class TemplateInvalid(TemplateError):
    pass


@dataclass
class TemplateRecord:
    name: str
    code: str
    body_sha256: str
    description: str = ""
    parameters: list[dict[str, Any]] | None = None
    version: int = 1
    created_at: str | None = None
    created_tick: int | None = None
    times_run: int = 0
    last_used_tick: int | None = None
    scope: str | None = None

    def parameter_names(self) -> list[str]:
        return [str(spec.get("name")) for spec in (self.parameters or [])]

    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameter_names(),
            "version": self.version,
            "body_sha256": self.body_sha256[:12],
            "times_run": self.times_run,
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_db_path() -> Path:
    return Path(os.environ.get("FLE_TEMPLATE_DB", ".fle/templates.db"))


def validate_name(name: str) -> str:
    if not isinstance(name, str) or not _NAME_PATTERN.match(name):
        raise TemplateInvalid(
            f"Invalid template name {name!r}: use 1-64 chars of [A-Za-z0-9_.-]"
        )
    return name


def validate_parameters(parameters: Any) -> list[dict[str, Any]]:
    """Normalize and validate the parameter list.

    Every parameter must be an object with ``name`` and a JSON ``default`` so
    that a saved template is always runnable and validatable.
    """

    if parameters is None:
        return []
    if not isinstance(parameters, list):
        raise TemplateInvalid("Template parameters must be a list")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for spec in parameters:
        if not isinstance(spec, dict):
            raise TemplateInvalid("Each template parameter must be an object")
        name = spec.get("name")
        if not isinstance(name, str) or not _PARAMETER_PATTERN.match(name):
            raise TemplateInvalid(
                f"Invalid parameter name {name!r}: use [A-Za-z_][A-Za-z0-9_]*"
            )
        if name in seen:
            raise TemplateInvalid(f"Duplicate parameter {name!r}")
        if "default" not in spec:
            raise TemplateInvalid(
                f"Parameter {name!r} must declare a default so the template "
                "is runnable and policy-validatable when saved"
            )
        seen.add(name)
        normalized.append(
            {
                "name": name,
                "description": str(spec.get("description", "")),
                "default": spec["default"],
            }
        )
    return normalized


def validate_body(body: str) -> tuple[str, str]:
    if not isinstance(body, str) or not body.strip():
        raise TemplateInvalid("Template code must be a non-empty string")
    if len(body.encode("utf-8")) > MAX_TEMPLATE_BYTES:
        raise TemplateInvalid(f"Template code exceeds {MAX_TEMPLATE_BYTES} byte limit")
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return body, digest


def _literal(value: Any) -> str:
    """Serialize one JSON value as a restricted Python literal.

    Only JSON-compatible scalars, arrays, and objects are accepted.  Strings
    are JSON-escaped (valid Python too) and containers recurse.
    """

    if value is None:
        return "None"
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TemplateInvalid("Numeric template arguments must be finite")
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_literal(item) for item in value) + "]"
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            if not isinstance(key, str):
                raise TemplateInvalid("Object template arguments need string keys")
            parts.append(f"{json.dumps(key)}: {_literal(item)}")
        return "{" + ", ".join(parts) + "}"
    raise TemplateInvalid(
        f"Unsupported template argument type {type(value).__name__}; use JSON values"
    )


def expand_template(
    code: str,
    parameters: list[dict[str, Any]] | None,
    arguments: dict[str, Any] | None = None,
) -> str:
    """Substitute ``{{name}}`` placeholders with literal argument values."""

    declared = {str(spec["name"]): spec for spec in (parameters or [])}
    supplied = dict(arguments or {})
    unknown = sorted(set(supplied) - set(declared))
    if unknown:
        raise TemplateInvalid("Unknown template parameters: " + ", ".join(unknown))
    values: dict[str, Any] = {}
    for name, spec in declared.items():
        if name in supplied:
            values[name] = supplied[name]
        else:
            values[name] = spec["default"]

    def _substitute(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in declared:
            raise TemplateInvalid(
                f"Template code references undeclared parameter {name!r}"
            )
        return _literal(values[name])

    return _PLACEHOLDER_PATTERN.sub(_substitute, code)


class ProgramTemplateStore:
    """Durable (SQLite) or ephemeral (in-memory) program template storage."""

    def __init__(
        self,
        scope: str | None,
        db_path: Path | str | None = None,
        max_per_scope: int = DEFAULT_MAX_PER_SCOPE,
    ):
        self.scope = scope
        self.max_per_scope = max(1, max_per_scope)
        self._lock = threading.Lock()
        if scope is None:
            self._db_path = None
            self._memory: dict[str, TemplateRecord] = {}
        else:
            path = Path(db_path) if db_path else default_db_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            self._db_path = path
            with self._connect() as conn:
                conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    @property
    def persistent(self) -> bool:
        return self.scope is not None

    def save(
        self,
        name: str,
        code: str,
        *,
        description: str = "",
        parameters: Any = None,
        created_tick: int | None = None,
    ) -> TemplateRecord:
        validate_name(name)
        code, digest = validate_body(code)
        normalized = validate_parameters(parameters)
        with self._lock:
            existing = self._get(name)
            if existing is None and self.count() >= self.max_per_scope:
                raise TemplateQuotaExceeded(
                    f"Scope {self.scope!r} holds {self.count()} templates "
                    f"(limit {self.max_per_scope}); delete or reuse a name"
                )
            version = (existing.version + 1) if existing is not None else 1
            record = TemplateRecord(
                name=name,
                code=code,
                body_sha256=digest,
                description=str(description or ""),
                parameters=normalized,
                version=version,
                created_at=_now(),
                created_tick=created_tick,
                times_run=(existing.times_run if existing else 0),
                last_used_tick=(existing.last_used_tick if existing else None),
                scope=self.scope,
            )
            if self.persistent:
                with self._connect() as conn:
                    conn.execute(
                        """
                        INSERT INTO program_templates (
                            scope, name, description, parameters, code,
                            body_sha256, version, created_at, created_tick,
                            times_run, last_used_tick
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(scope, name) DO UPDATE SET
                            description = excluded.description,
                            parameters = excluded.parameters,
                            code = excluded.code,
                            body_sha256 = excluded.body_sha256,
                            version = excluded.version,
                            created_at = excluded.created_at,
                            created_tick = excluded.created_tick
                        """,
                        (
                            self.scope,
                            name,
                            record.description,
                            json.dumps(normalized),
                            code,
                            digest,
                            version,
                            record.created_at,
                            created_tick,
                            record.times_run,
                            record.last_used_tick,
                        ),
                    )
            else:
                self._memory[name] = record
            return record

    def get(self, name: str) -> TemplateRecord:
        validate_name(name)
        with self._lock:
            record = self._get(name)
        if record is None:
            raise TemplateNotFound(f"No program template named {name!r} in scope")
        return record

    def try_get(self, name: str) -> TemplateRecord | None:
        try:
            return self.get(name)
        except (TemplateNotFound, TemplateInvalid):
            return None

    def delete(self, name: str) -> bool:
        validate_name(name)
        with self._lock:
            if not self.persistent:
                return self._memory.pop(name, None) is not None
            with self._connect() as conn:
                cursor = conn.execute(
                    "DELETE FROM program_templates WHERE scope = ? AND name = ?",
                    (self.scope, name),
                )
                return cursor.rowcount > 0

    def list_summaries(self) -> list[dict[str, Any]]:
        if not self.persistent:
            with self._lock:
                records = list(self._memory.values())
            return [
                record.summary() for record in sorted(records, key=lambda r: r.name)
            ]
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT name, description, parameters, version, body_sha256,
                       times_run
                FROM program_templates WHERE scope = ? ORDER BY name
                """,
                (self.scope,),
            ).fetchall()
        summaries = []
        for row in rows:
            specs = json.loads(row[2] or "[]")
            summaries.append(
                {
                    "name": row[0],
                    "description": row[1],
                    "parameters": [spec.get("name") for spec in specs],
                    "version": row[3],
                    "body_sha256": row[4][:12],
                    "times_run": row[5],
                }
            )
        return summaries

    def count(self) -> int:
        if not self.persistent:
            return len(self._memory)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM program_templates WHERE scope = ?",
                (self.scope,),
            ).fetchone()
        return int(row[0]) if row else 0

    def record_run(
        self, name: str, tick: int | None, lease_id: str | None = None
    ) -> None:
        with self._lock:
            if not self.persistent:
                record = self._memory.get(name)
                if record is not None:
                    record.times_run += 1
                    record.last_used_tick = tick
                return
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE program_templates
                    SET times_run = times_run + 1,
                        last_used_tick = ?,
                        last_used_lease = ?
                    WHERE scope = ? AND name = ?
                    """,
                    (tick, lease_id, self.scope, name),
                )

    def _get(self, name: str) -> TemplateRecord | None:
        if not self.persistent:
            return self._memory.get(name)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT name, description, parameters, code, body_sha256,
                       version, created_at, created_tick, times_run,
                       last_used_tick
                FROM program_templates WHERE scope = ? AND name = ?
                """,
                (self.scope, name),
            ).fetchone()
        if row is None:
            return None
        return TemplateRecord(
            name=row[0],
            description=row[1],
            parameters=json.loads(row[2] or "[]"),
            code=row[3],
            body_sha256=row[4],
            version=row[5],
            created_at=row[6],
            created_tick=row[7],
            times_run=row[8],
            last_used_tick=row[9],
            scope=self.scope,
        )

    def drop_scope(self) -> int:
        """Delete every template in this scope (generation retirement)."""
        with self._lock:
            if not self.persistent:
                dropped = len(self._memory)
                self._memory.clear()
                return dropped
            with self._connect() as conn:
                cursor = conn.execute(
                    "DELETE FROM program_templates WHERE scope = ?",
                    (self.scope,),
                )
                return cursor.rowcount


__all__ = [
    "DEFAULT_MAX_PER_SCOPE",
    "MAX_TEMPLATE_BYTES",
    "TEMPLATE_STORE_VERSION",
    "ProgramTemplateStore",
    "TemplateError",
    "TemplateInvalid",
    "TemplateNotFound",
    "TemplateQuotaExceeded",
    "TemplateRecord",
    "default_db_path",
    "expand_template",
    "validate_parameters",
]
