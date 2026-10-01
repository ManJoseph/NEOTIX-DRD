"""Create the configured database if absent; never replace existing data."""
import os
from pathlib import Path

import psycopg
from psycopg import sql
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
database_name = os.environ["DB_NAME"]
try:
    with psycopg.connect(
        dbname="postgres", user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
        host=os.getenv("DB_HOST", "localhost"), port=os.getenv("DB_PORT", "5432"),
        autocommit=True, connect_timeout=5,
    ) as connection:
        exists = connection.execute("SELECT 1 FROM pg_database WHERE datname = %s", [database_name]).fetchone()
        if not exists:
            connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
            print("Created application database.")
        else:
            print("Application database already exists; keeping existing data.")
except psycopg.Error:
    raise SystemExit("Database setup failed. Check PostgreSQL, .env, and database creation permissions.")
