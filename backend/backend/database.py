from contextlib import contextmanager

from config import get_settings
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

_engine = None
_session_local = None


def _get_engine():
    """Create engine lazily so tests can override DATABASE_URL first."""
    global _engine, _session_local
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
        _session_local = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine, _session_local


def reset_engine() -> None:
    """Dispose engine and force recreation. Called by test fixtures."""
    global _engine, _session_local
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_local = None


@contextmanager
def get_db():
    _, session_local = _get_engine()
    db: Session = session_local()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def execute_query(query: str, params: dict | None = None) -> list[dict]:
    with get_db() as db:
        result = db.execute(text(query), params or {})
        if result.returns_rows:
            cols = result.keys()
            return [dict(zip(cols, row, strict=False)) for row in result.fetchall()]
        return []


def execute_write(query: str, params: dict | None = None) -> None:
    with get_db() as db:
        db.execute(text(query), params or {})
