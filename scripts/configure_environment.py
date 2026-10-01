"""Create local development configuration only when .env is missing."""
import getpass
import json
from pathlib import Path

from django.core.management.utils import get_random_secret_key

root = Path(__file__).resolve().parent.parent
path = root / ".env"
if not path.exists():
    print("Configure your local PostgreSQL connection. Secrets stay in ignored .env.")
    values = {
        "DJANGO_SECRET_KEY": get_random_secret_key(),
        "DJANGO_DEBUG": "True",
        "DB_NAME": input("Database name [neotix_drd]: ").strip() or "neotix_drd",
        "DB_USER": input("Database user [postgres]: ").strip() or "postgres",
        "DB_PASSWORD": getpass.getpass("Database password: "),
        "DB_HOST": input("Database host [localhost]: ").strip() or "localhost",
        "DB_PORT": input("Database port [5432]: ").strip() or "5432",
    }
    path.write_text("\n".join(f"{key}={json.dumps(value)}" for key, value in values.items()) + "\n", encoding="utf-8")
    print("Created local .env. No credentials are published.")
else:
    print("Using existing local .env.")
