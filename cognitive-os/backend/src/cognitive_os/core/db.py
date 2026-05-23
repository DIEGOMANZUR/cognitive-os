from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from cognitive_os.core.config import settings

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for operational PostgreSQL models.

    `eager_defaults=True` makes INSERT/UPDATE emit a RETURNING clause for
    server-side defaults (e.g. `created_at`, `updated_at` on `TimestampMixin`).
    Without it, reading those attributes after `await session.flush()` in an
    async session triggers a lazy refresh outside the greenlet boundary and
    raises `sqlalchemy.exc.MissingGreenlet`. This is the canonical async-safe
    setting per SQLAlchemy 2.x docs and is the surgical fix for the
    `_view(action_request)` call sites in `actions/service.py`.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    __mapper_args__ = {"eager_defaults": True}


engine = create_async_engine(settings.database_url, pool_pre_ping=True, poolclass=NullPool)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Provide an async transactional SQLAlchemy session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
