from logging.config import fileConfig

from sqlalchemy import engine_from_config, create_engine
from sqlalchemy import pool

from alembic import context

import os
import sys


repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

sys.path.insert(0, os.path.join(repo_root, "src"))


from dotenv import load_dotenv, find_dotenv


from app.db.base import Base


dotenv_path = find_dotenv(usecwd=True)
if not dotenv_path:
    raise FileNotFoundError(".env не знайдено")
load_dotenv(dotenv_path, override=True)

config = context.config

user = os.getenv("POSTGRES_USER", "").strip()
pwd  = os.getenv("POSTGRES_PASSWORD", "").strip()
host = os.getenv("POSTGRES_HOST", "").strip()
port = os.getenv("POSTGRES_DB_PORT", "").strip()
db   = os.getenv("POSTGRES_DB", "").strip()

database_url = f"postgresql+pg8000://{user}:{pwd}@{host}:{port}/{db}"
config.set_main_option("sqlalchemy.url", database_url)


if config.config_file_name is not None:
    fileConfig(config.config_file_name)

import app.models.user_models
import app.models.movie_models
import app.models.cart_models
import app.models.order_models
target_metadata = Base.metadata



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
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(
        database_url,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
