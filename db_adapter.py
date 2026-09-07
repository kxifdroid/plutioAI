"""Database adapter supporting both SQLite and Supabase PostgreSQL.

Provides transparent translation of query parameters, robust SSL handling,
row mapping matching sqlite3.Row, and schema initialization.
"""

from __future__ import annotations

import os
import re
import json
import logging
import sqlite3
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

_raw_sqlite3_connect = sqlite3.connect

try:
    import psycopg2
    from psycopg2 import extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False


NO_ID_TABLES = {"time_slot_platforms", "platform_daily_limits"}


def is_postgres() -> bool:
    """Check if PostgreSQL/Supabase is configured."""
    return bool(
        os.environ.get("DATABASE_URL")
        or os.environ.get("SUPABASE_DB_URL")
        or os.environ.get("POSTGRES_URL")
    )


def get_postgres_url() -> Optional[str]:
    """Retrieve normalized PostgreSQL connection URI with required SSL settings."""
    url = (
        os.environ.get("DATABASE_URL")
        or os.environ.get("SUPABASE_DB_URL")
        or os.environ.get("POSTGRES_URL")
    )
    if not url:
        return None
    url = url.strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    
    # Supabase and cloud PostgreSQL require SSL
    if "sslmode=" not in url and ("supabase" in url or "amazonaws" in url or "neon" in url or "render" in url):
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}sslmode=require"
    return url


class PostgresRow:
    """Row wrapper providing dict-like, attribute-like, and index-based access."""

    def __init__(self, description: Any, values: Tuple[Any, ...]):
        self._keys = [col.name.lower() for col in description] if description else []
        self._tuple = list(values) if values is not None else []
        self._map = {k: v for k, v in zip(self._keys, self._tuple)}

    def __getitem__(self, key: Union[int, str]) -> Any:
        if isinstance(key, int):
            return self._tuple[key]
        return self._map[str(key).lower()]

    def __setitem__(self, key: Union[int, str], value: Any) -> None:
        if isinstance(key, int):
            self._tuple[key] = value
            if key < len(self._keys):
                self._map[self._keys[key]] = value
        else:
            k = str(key).lower()
            self._map[k] = value
            if k in self._keys:
                idx = self._keys.index(k)
                self._tuple[idx] = value

    def __contains__(self, key: str) -> bool:
        return str(key).lower() in self._map

    def get(self, key: str, default: Any = None) -> Any:
        return self._map.get(str(key).lower(), default)

    def keys(self) -> List[str]:
        return list(self._keys)

    def values(self) -> List[Any]:
        return list(self._tuple)

    def items(self) -> List[Tuple[str, Any]]:
        return list(self._map.items())

    def __iter__(self):
        return iter(self._tuple)

    def __len__(self) -> int:
        return len(self._tuple)

    def __repr__(self) -> str:
        return f"<PostgresRow {self._map}>"


def translate_query(sql: str) -> Tuple[str, bool]:
    """Translate SQLite query dialect into PostgreSQL dialect."""
    s = sql.strip()

    # 1. Handle INSERT OR REPLACE INTO episodes
    if re.search(r'INSERT\s+OR\s+REPLACE\s+INTO\s+episodes', s, re.IGNORECASE):
        match = re.search(
            r'INSERT\s+OR\s+REPLACE\s+INTO\s+episodes\s*\((.*?)\)\s*VALUES\s*\((.*?)\)',
            s,
            re.IGNORECASE | re.DOTALL
        )
        if match:
            cols_str, vals_str = match.group(1), match.group(2)
            cols = [c.strip() for c in cols_str.split(',')]
            update_set = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c.lower() != 'url')
            s = f"INSERT INTO episodes ({cols_str}) VALUES ({vals_str}) ON CONFLICT (url) DO UPDATE SET {update_set}"

    # 2. Handle INSERT OR IGNORE INTO ...
    if re.search(r'INSERT\s+OR\s+IGNORE\s+INTO\s+', s, re.IGNORECASE):
        s = re.sub(r'INSERT\s+OR\s+IGNORE\s+INTO\s+', 'INSERT INTO ', s, flags=re.IGNORECASE)
        if 'ON CONFLICT' not in s.upper():
            s = s.rstrip(';') + ' ON CONFLICT DO NOTHING'

    # 3. Translate '?' placeholders to '%s' (preserving strings)
    result = []
    in_quote = False
    quote_char = None
    for char in s:
        if in_quote:
            result.append(char)
            if char == quote_char:
                in_quote = False
        else:
            if char in ("'", '"'):
                in_quote = True
                quote_char = char
                result.append(char)
            elif char == '?':
                result.append('%s')
            else:
                result.append(char)
    translated_sql = "".join(result)

    # 4. Check if RETURNING id should be appended for lastrowid
    is_insert = translated_sql.strip().upper().startswith("INSERT INTO")
    has_returning = "RETURNING" in translated_sql.upper()
    
    table_match = re.search(r'INSERT\s+INTO\s+([a-zA-Z0-9_]+)', translated_sql, re.IGNORECASE)
    table_name = table_match.group(1).lower() if table_match else ""
    
    append_returning = is_insert and not has_returning and table_name not in NO_ID_TABLES
    if append_returning:
        translated_sql = translated_sql.rstrip(';') + ' RETURNING id'

    return translated_sql, append_returning


class PostgresCursorWrapper:
    """Wrapper around psycopg2 cursor matching sqlite3 cursor interface."""

    def __init__(self, raw_cursor: Any):
        self._cur = raw_cursor
        self.lastrowid: Optional[int] = None
        self._description = None

    @property
    def description(self):
        return self._cur.description

    @property
    def rowcount(self):
        return self._cur.rowcount

    def execute(self, sql: str, params: Union[Tuple, List, Dict] = ()):
        translated_sql, appended_returning = translate_query(sql)
        
        if params is None:
            params = ()
        elif isinstance(params, (list, tuple)):
            converted_params = []
            for p in params:
                converted_params.append(p)
            params = tuple(converted_params)

        try:
            self._cur.execute(translated_sql, params)
        except Exception as e:
            if appended_returning and 'column "id" does not exist' in str(e).lower():
                self._cur.connection.rollback()
                sql_no_returning, _ = translate_query(sql)
                sql_no_returning = re.sub(r'\s+RETURNING\s+id', '', sql_no_returning, flags=re.IGNORECASE)
                self._cur.execute(sql_no_returning, params)
                self.lastrowid = None
                return self
            raise

        if appended_returning:
            try:
                row = self._cur.fetchone()
                if row and len(row) > 0:
                    self.lastrowid = row[0]
            except Exception:
                self.lastrowid = None
        else:
            self.lastrowid = None

        return self

    def executemany(self, sql: str, seq_of_parameters: Iterable[Any]):
        translated_sql, _ = translate_query(sql)
        return self._cur.executemany(translated_sql, seq_of_parameters)

    def fetchone(self) -> Optional[PostgresRow]:
        row = self._cur.fetchone()
        if row is None:
            return None
        return PostgresRow(self._cur.description, row)

    def fetchall(self) -> List[PostgresRow]:
        rows = self._cur.fetchall()
        if not rows:
            return []
        desc = self._cur.description
        return [PostgresRow(desc, r) for r in rows]

    def fetchmany(self, size: int = 1) -> List[PostgresRow]:
        rows = self._cur.fetchmany(size)
        if not rows:
            return []
        desc = self._cur.description
        return [PostgresRow(desc, r) for r in rows]

    def close(self):
        try:
            self._cur.close()
        except Exception:
            pass


class PostgresConnectionWrapper:
    """Wrapper around psycopg2 connection matching sqlite3 connection interface."""

    def __init__(self, raw_conn: Any):
        self._conn = raw_conn
        self.row_factory = None

    def cursor(self) -> PostgresCursorWrapper:
        return PostgresCursorWrapper(self._conn.cursor())

    def execute(self, sql: str, params: Union[Tuple, List, Dict] = ()) -> PostgresCursorWrapper:
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def executemany(self, sql: str, seq_of_parameters: Iterable[Any]) -> PostgresCursorWrapper:
        cur = self.cursor()
        cur.executemany(sql, seq_of_parameters)
        return cur

    def commit(self):
        try:
            self._conn.commit()
        except Exception as e:
            logger.error("Commit failed: %s", e)

    def rollback(self):
        try:
            self._conn.rollback()
        except Exception:
            pass

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


def connect(db_path: str = "insights.db") -> Union[PostgresConnectionWrapper, sqlite3.Connection]:
    """Return database connection: Supabase PostgreSQL if configured, else SQLite."""
    if is_postgres():
        if not HAS_PSYCOPG2:
            raise RuntimeError(
                "PostgreSQL / Supabase connection requested via DATABASE_URL, "
                "but psycopg2-binary is not installed."
            )
        db_url = get_postgres_url()
        raw_conn = psycopg2.connect(db_url, connect_timeout=10)
        raw_conn.autocommit = False
        return PostgresConnectionWrapper(raw_conn)
    else:
        conn = _raw_sqlite3_connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
