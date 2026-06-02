# This configuration is for illustrative purposes only.
# Please do not use it as is in production.
import os

from django.utils.translation import gettext_lazy as _

PUBLIC_URL = os.getenv("PUBLIC_URL", "127.0.0.1")
ALLOWED_HOSTS = ["127.0.0.1", locals().get("PUBLIC_URL", "")]
REGULATOR_CONTACT = {
    "name": "Organization Name",
    "street": "Organization Street",
    "zip_code": "Organization Zip Code",
    "city": "city",
    "mail_zip_code": "Organization Zip Code",
    "mail_city": "city",
    "country": "Organization Country",
    "phone": "Organization Phone Number",
    "website": "https://www.example.org",
    "short_url": "example.org",
    "contact_email": "contact@example.org",
    "privacy_email": "privacy@exemple.org",
    "tos_url": None,  # "https://www.example.org/tos"
    "privacy_policy_url": None,  # "https://www.example.org/privacy_policy"
    "contact_url": None,  # "https://www.example.org/contact_us"
}

# The generic site/tool name. Used to load specific config, templates, styles, logo.
SITE_NAME = "SERIMA"

SECRET_KEY = "itl44kw2RCMArqCn2XSx1Mo7d28TvKLeCon9KaSeUSI8CzeUXu"
HASH_KEY = b"Xaj5lFGAPiy2Ovzi4YmlWh-s4HHikFV4AswilOPPYN8="

DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "t")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "serima-governance"),
        "USER": os.getenv("POSTGRES_USER", "<user>"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "<password>"),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": int(os.getenv("POSTGRES_PORT", "5432")),
    },
}

CSRF_TRUSTED_ORIGINS: list[str] = []
CORS_ALLOWED_ORIGINS: list[str] = []
CORS_ALLOWED_ORIGIN_REGEXES: list[str] = []
CORS_ALLOW_METHODS = [
    "GET",
    "OPTIONS",
]

EMAIL_HOST = "localhost"
EMAIL_PORT = 25
EMAIL_SENDER = "no-reply@monarc.lu"

API_ENABLED = False

# business configuration
MAX_PRELIMINARY_NOTIFICATION_PER_DAY_PER_USER = 3

# Logging mechanism
LOG_DIRECTORY = "./logs"
LOG_FILE = "django.log"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "root": {"level": "INFO", "handlers": ["file"]},
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": os.path.join(LOG_DIRECTORY, LOG_FILE),
            "formatter": "app",
        },
    },
    "loggers": {
        "django": {"handlers": ["file"], "level": "INFO", "propagate": True},
    },
    "formatters": {
        "app": {
            "format": ("%(asctime)s [%(levelname)-8s] (%(module)s.%(funcName)s) %(message)s"),
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
}

LOG_RETENTION_TIME_IN_DAY = 365
INCIDENT_RETENTION_TIME_IN_DAY = 1825
TERMS_ACCEPTANCE_TIME_IN_DAYS = 365

# TIMEOUT
SESSION_COOKIE_AGE = 15 * 60  # 15 Minutes
CSRF_COOKIE_AGE = 15 * 60

# INTERNATIONALIZATION
LANGUAGE_CODE = "en-us"

TIME_ZONE = "Europe/Luxembourg"

LANGUAGES = [
    ("en", "English"),
    ("fr", "French"),
    ("nl", _("Dutch")),
    ("de", "German"),
]

PARLER_DEFAULT_LANGUAGE_CODE = "en"
PARLER_LANGUAGES = {
    1: (
        {
            "code": "en",
        },  # English
        {
            "code": "fr",
        },  # French
        {
            "code": "nl",
        },  # Dutch
        {
            "code": "de",
        },  # German
    ),
}

# COOKIEBANNER
COOKIEBANNER = {
    "title": _("Cookie Notice"),
    "groups": [
        {
            "id": "essential",
            "name": _("Essential"),
            "description": _(
                "This website uses cookies and similar technologies essential for its operation. \
                It does not process personal data. By clicking ‘Accept’, \
                you consent to the use of cookies. For more details, please see:"
            ),
            "cookies": [
                {
                    "pattern": "cookiebanner",
                    "description": _("Cookie used to store the user’s consent to the use of cookies."),
                    "content": _("The user’s cookie preferences."),
                    "max_age": _("6 months"),  # Set in cookie_banner.js
                },
                {
                    "pattern": "sessionid",
                    "description": _("Cookie essential for maintaining user session options."),
                    "content": _("Session ID"),
                    "max_age": _("15 minutes"),  # SESSION_COOKIE_AGE
                },
                {
                    "pattern": "csrftoken",
                    "description": _("Cookie used to prevent Cross-Site Request Forgery (CSRF) attacks."),
                    "content": _("Token"),
                    "max_age": _("15 minutes"),  # CSRF_COOKIE_AGE
                },
                {
                    "pattern": "django_language",
                    "description": _("Cookie used to store user language preferences."),
                    "content": _("Language settings"),
                    "max_age": _("Session"),
                },
                {
                    "pattern": "theme",
                    "description": _("Cookie used to store user theme preferences."),
                    "content": _("Dark/light theme settings"),
                    "max_age": _("Session"),
                },
            ],
        }
    ],
}

# HSTS
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# SSL enforcement
SECURE_SSL_REDIRECT = False  # redirect HTTP to HTTPS
SESSION_COOKIE_SECURE = False  # Cookies are sent via HTTPS
CSRF_COOKIE_SECURE = False  # Secure CSRF via HTTPS
LANGUAGE_COOKIE_SECURE = False  # Secure language cookie via HTTPS
SECURE_PROXY_SSL_HEADER = None  # SSL proxy used e.g: ("HTTP_X_FORWARDED_PROTO", "https")

# Cookies configuration for HTTPONLY
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
LANGUAGE_COOKIE_HTTPONLY = True

# samesite configuration for cookies
SESSION_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_SAMESITE = "Strict"
LANGUAGE_COOKIE_SAMESITE = "Strict"

# password reset link timeout
PASSWORD_RESET_TIMEOUT = 1800

# CELERY config
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/1"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
PATH_FOR_REPORTING_PDF = f"{os.getcwd()}/tmp/"

# Email adress for contact form
EMAIL_FOR_CONTACT = REGULATOR_CONTACT["contact_email"]
# Email adress for FROM field and RETURN-PATH
EMAIL_CONTACT_FROM = "test@mail.localhost"
# Captcha settings
CAPTCHA_FONT_SIZE = 30

# Clickjacking
X_FRAME_OPTIONS = "DENY"

# MIME sniffing
SECURE_CONTENT_TYPE_NOSNIFF = True  # => X-Content-Type-Options: nosniff

# Referrer Policy
REFERRER_POLICY = "strict-origin-when-cross-origin"
