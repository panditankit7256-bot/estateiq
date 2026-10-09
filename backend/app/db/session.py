from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from ..core.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")
engine = create_engine(settings.database_url, future=True,
                       connect_args={"check_same_thread": False} if _is_sqlite else {})
if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _pragma(conn, _):
        cur = conn.cursor(); cur.execute("PRAGMA journal_mode=WAL"); cur.execute("PRAGMA synchronous=NORMAL"); cur.close()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass
