import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from dotenv import load_dotenv

# --- Start of custom configuration ---

# Add project root to sys.path to allow imports from 'backend'
# This assumes env.py is in backend/migrations
script_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(script_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now we can import from the 'backend' package
from backend.extensions import db

# Load .env file for local execution
# This will load variables from /backend/.env
load_dotenv(os.path.join(project_root, 'backend', '.env'))

# --- End of custom configuration ---

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- Database URL Configuration ---

# Get the database URL from environment variables, mirroring app.py
db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith('mysql://'):
    db_url = db_url.replace('mysql://', 'mysql+pymysql://', 1)
else:
    # Fallback for local development or other environments
    MYSQL_USER = os.environ.get("MYSQL_USER")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "") # Handles empty password
    MYSQL_HOST = os.environ.get("MYSQL_HOST")
    MYSQL_PORT = os.environ.get("MYSQL_PORT")
    MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE")

    if all([MYSQL_USER, MYSQL_HOST, MYSQL_PORT, MYSQL_DATABASE]):
        db_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"

# If db_url is still not set, we cannot proceed.
if not db_url:
    raise RuntimeError(
        "Database URL could not be determined for migration. "
        "Ensure DATABASE_URL or individual MYSQL_* variables are set."
    )

# Set the database URL for Alembic. Ensure it's a string.
config.set_main_option('sqlalchemy.url', str(db_url))

# add your model's MetaData object here for 'autogenerate' support
target_metadata = db.metadata

# --- Alembic runtime configuration ---

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
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
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

