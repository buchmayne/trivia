"""Standalone, disposable studio site. Never import the normal project settings here."""

from pathlib import Path
import secrets

BASE_DIR = Path(__file__).resolve().parent.parent
SANDBOX_DIR = BASE_DIR / ".studio-sandbox"
SANDBOX_DIR.mkdir(mode=0o700, exist_ok=True)

# Persist the local signing key so sessions survive a server restart. It is
# deleted with the sandbox; no production credentials or .env are consulted.
key_file = SANDBOX_DIR / "secret_key"
if not key_file.exists():
    try:
        with key_file.open("x") as key:
            key.write(secrets.token_urlsafe(48))
        key_file.chmod(0o600)
    except FileExistsError:
        pass
SECRET_KEY = key_file.read_text().strip()

DEBUG = True
ENABLE_V2_STUDIO = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]
ROOT_URLCONF = "studio_sandbox.urls"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "studio",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "studio_sandbox" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": SANDBOX_DIR / "studio.sqlite3",
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/studio/"
SESSION_COOKIE_NAME = "studio_sandbox_session"
CSRF_COOKIE_NAME = "studio_sandbox_csrf"
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

MEDIA_URL = "/sandbox-media/"
MEDIA_ROOT = SANDBOX_DIR / "media"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": str(MEDIA_ROOT), "base_url": MEDIA_URL},
    },
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
STATIC_URL = "/static/"
