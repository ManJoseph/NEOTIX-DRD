"""Create local development configuration only when .env is missing."""
import getpass
import json
import os
from pathlib import Path

from django.core.management.utils import get_random_secret_key

root = Path(__file__).resolve().parent.parent
path = root / ".env"
if not path.exists():
    print("Configure your local PostgreSQL connection. Secrets stay in ignored .env.")
    values = {
        "DJANGO_SECRET_KEY": get_random_secret_key(),
        "DJANGO_DEBUG": "True",
        "DB_NAME": os.getenv("DB_NAME") or input("Database name [neotix_drd]: ").strip() or "neotix_drd",
        "DB_USER": os.getenv("DB_USER") or input("Database user [postgres]: ").strip() or "postgres",
        "DB_PASSWORD": os.environ["DB_PASSWORD"] if "DB_PASSWORD" in os.environ else getpass.getpass("Database password: "),
        "DB_HOST": os.getenv("DB_HOST") or input("Database host [localhost]: ").strip() or "localhost",
        "DB_PORT": os.getenv("DB_PORT") or input("Database port [5432]: ").strip() or "5432",
    }
    path.write_text("\n".join(f"{key}={json.dumps(value)}" for key, value in values.items()) + "\n", encoding="utf-8")
    print("Created local .env. No credentials are published.")
else:
    print("Using existing local .env.")
