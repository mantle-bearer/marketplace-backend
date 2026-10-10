from decouple import Csv, config

SECRET_KEY = config(
    "SECRET_KEY",
    default="django-insecure-)!)!%4a1o9xb=1mjy9r5w^oc!+)trcgq35ur^+)a^1rnb+f&1n",
)
DEBUG = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

DATABASE_NAME = config("DATABASE_NAME", default="marketplace_db")
DATABASE_USER = config("DATABASE_USER", default="postgres")
DATABASE_PASSWORD = config("DATABASE_PASSWORD", default="postgres")
DATABASE_HOST = config("DATABASE_HOST", default="127.0.0.1")
DATABASE_PORT = config("DATABASE_PORT", default="5432")

REDIS_URL = config("REDIS_URL", default="redis://localhost:6379/0").rstrip("/")
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default=REDIS_URL).rstrip("/")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default=REDIS_URL).rstrip("/")

WEBHOOK_SECRET = config("WEBHOOK_SECRET", default="super-secret-webhook-key-12345")