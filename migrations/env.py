import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Додаємо папку src до sys.path, щоб імпорти з "app" працювали
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

# Імпортуємо Base та всі моделі для автогенерації
from app.db.base import Base
import app.models.user_models
import app.models.movie_models
import app.models.cart_models
import app.models.order_models

# Налаштування Alembic
config = context.config

# Зчитуємо DATABASE_URL із середовища (CI/CD або локально через .env)
database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL environment variable is not set")
# Alembic потребує синхронного драйвера, тож міняємо +asyncpg на стандартний
sync_url = database_url.replace("+asyncpg", "")
config.set_main_option("sqlalchemy.url", sync_url)

# Налаштовуємо логування
if config.config_file_name:
    fileConfig(config.config_file_name)

# Мета-дані для автогенерації
target_metadata = Base.metadata


def run_migrations_offline() -> None:
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
    engine = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with engine.connect() as connection:
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
