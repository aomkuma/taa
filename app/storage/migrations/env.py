"""Alembic environment. The URL is injected by app.storage.database.upgrade_schema or -x url=..."""

from __future__ import annotations

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.storage.models import Base

config = context.config
target_metadata = Base.metadata

x_url = context.get_x_argument(as_dictionary=True).get("url")
if x_url:
    config.set_main_option("sqlalchemy.url", x_url)


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section) or {}, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
