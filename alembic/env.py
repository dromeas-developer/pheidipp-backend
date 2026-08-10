from logging.config import fileConfig

from sqlalchemy import create_engine
from sqlalchemy import pool

from alembic import context

from app.db.base import Base
from app.config import get_postgres_url, settings

# Import all model modules so their tables register with Base.metadata.
# Without this, Alembic autogenerate sees an empty metadata and
# generates false-positive "remove all tables" every time.
import app.models  # noqa: F401 — side-effect import for metadata registration

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def include_object(obj, name, type_, reflected, compare_to):
    """
    Exclude procrastinate-managed objects from autogenerate.

    Procrastinate owns its own schema (tables, indexes, enums, functions)
    installed via `procrastinate schema --install`, not via Alembic.

    Without this filter, Alembic autogenerate sees these objects in the
    database but not in Base.metadata, and generates phantom drop/create
    operations for them in every migration.
    """
    if type_ == "table" and name.startswith("procrastinate_"):
        return False
    if type_ == "index" and name.startswith("procrastinate_"):
        return False
    if type_ == "type" and name.startswith("procrastinate_"):
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        url = str(settings.DATABASE_URL).replace(
            "postgresql+asyncpg", "postgresql+psycopg2"
        )
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = create_engine(get_postgres_url(sync=True), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
