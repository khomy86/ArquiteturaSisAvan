from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from catalog_service import config as app_config
from catalog_service.models import Base

config = context.config

# Only set when Alembic is run from the command line; when the service runs
# migrations on startup it keeps its own logging setup.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


# The service passes in its own connection (see database.run_migrations) so
# the migration runs inside the transaction that holds its advisory lock.
connection = config.attributes.get("connection")
if connection is not None:
    run_migrations(connection)
else:
    engine = create_engine(app_config.DATABASE_URL, poolclass=pool.NullPool)
    with engine.connect() as connection:
        run_migrations(connection)
