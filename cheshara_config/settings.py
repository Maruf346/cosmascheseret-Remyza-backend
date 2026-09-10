from pathlib import Path
from datetime import timedelta
import os

BASE_DIR = Path(__file__).resolve().parent.parent

from dotenv import load_dotenv
ENV_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ENV_BASE_DIR, ".env"))

SECRET_KEY = os.getenv("SECRET_KEY")
DEBUG = os.getenv("DEBUG", "False").strip().lower() in ("true", "1", "yes")
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")
CSRF_TRUSTED_ORIGINS = os.getenv("CSRF_TRUSTED_ORIGINS", "*").split(",")


# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # library app-----
    'rest_framework', 'rest_framework_simplejwt',
    'corsheaders', 'django_extensions', 'django_filters',
    'rest_framework_simplejwt.token_blacklist',
    'drf_spectacular',
    
    # custom app-----
    'accounts', 'ai', 'business', 'common', 'communications', 'core', 'crm', 'subscription', 'twilio_app', 'sentdm'
]


# ================================================================================
# ==================== Rest Frame Work Configurations Start====================
ENABLE_BROWSABLE_API = os.getenv('ENABLE_BROWSABLE_API', 'False') == 'True'
if ENABLE_BROWSABLE_API:
    DEFAULT_RENDERER_CLASSES_ = [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ]
else:
    DEFAULT_RENDERER_CLASSES_ = [
        'rest_framework.renderers.JSONRenderer'
    ]

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': DEFAULT_RENDERER_CLASSES_,
    
    # 'EXCEPTION_HANDLER': 'core.exceptions.custom_exception_handler',
    
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    
    # 'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    # 'PAGE_SIZE': 5,
    
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
    ),

    'DEFAULT_SCHEMA_CLASS': 'core.schema.TaggedAutoSchema',
}

SIMPLE_JWT = {
    'AUTH_HEADER_TYPES': ('Bearer',),
    'BLACKLIST_AFTER_ROTATION': True,
    'ROTATE_REFRESH_TOKENS': True,
    # 'ROTATE_REFRESH_TOKENS': False,
    
    'ACCESS_TOKEN_LIFETIME': timedelta(days=60),
    # 'ACCESS_TOKEN_LIFETIME': timedelta(minutes=5),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=60),
    
    "UPDATE_LAST_LOGIN": True,
}

CORS_ORIGIN_ALLOW_ALL = True

SPECTACULAR_SETTINGS = {
    'TITLE': 'Chesera API',
    'DESCRIPTION': 'API documentation for Chesera project',
    'VERSION': '1.0.0',
    'TAGS': [
        {'name': 'Auth - Admin', 'description': 'Admin authentication endpoints.'},
        {'name': 'Auth - User', 'description': 'Client OTP authentication endpoints.'},
        {'name': 'Auth - Token', 'description': 'JWT refresh and verification endpoints.'},
        {'name': 'User Account', 'description': 'Current user profile and account management.'},
        {'name': 'User Plan Progress', 'description': 'Current user subscription and onboarding progress.'},
        {'name': 'Business', 'description': 'Business management, automation and reply settings.'},
        {'name': 'Notifications', 'description': 'User notification preferences.'},
        {'name': 'Sent.dm', 'description': 'Sent.dm sandbox, sender profile, message, and webhook endpoints.'},
        {'name': 'User Subscriptions', 'description': 'Apple/Google in-app subscription records and admin subscription review.'},
        {'name': 'Reference Data', 'description': 'Business type and industry reference data.'},
        {'name': 'API Schema', 'description': 'OpenAPI schema endpoint used by Swagger and ReDoc.'},
    ],    'SECURITY': [{'BearerAuth': []}],
    'COMPONENTS': {
        'SECURITY_SCHEMES': {
            'BearerAuth': {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
            }
        }
    },
}

# ==================== Rest Frame Work Configurations End====================
# ================================================================================


MIDDLEWARE = [
    # library middleware
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
ROOT_URLCONF = 'cheshara_config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'cheshara_config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

# Database
# Uses PostgreSQL in production (set DB_* env vars), SQLite for local dev.
if os.getenv('DB_NAME'):
    DATABASES = {
        'default': {
            'ENGINE': os.getenv('DB_ENGINE', 'django.db.backends.postgresql'),
            'NAME': os.getenv('DB_NAME'),
            'USER': os.getenv('DB_USER'),
            'PASSWORD': os.getenv('DB_PASSWORD'),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
            'CONN_MAX_AGE': 60,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]



# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []

# Media / Storage
# When USE_S3=True, media files are stored in AWS S3 via django-storages.
USE_S3 = os.getenv('USE_S3', 'False').strip().lower() in ('true', '1', 'yes')

if USE_S3:
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME', 'us-east-1')
    AWS_S3_CUSTOM_DOMAIN = os.getenv('AWS_S3_CUSTOM_DOMAIN', f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com')
    AWS_DEFAULT_ACL = None
    AWS_S3_OBJECT_PARAMETERS = {'CacheControl': 'max-age=86400'}
    AWS_QUERYSTRING_AUTH = False

    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/'
else:
    MEDIA_URL = 'media/'
    MEDIA_ROOT = os.getenv('MEDIA_ROOT', default=os.path.join(BASE_DIR, 'media'))

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'accounts.User'

# Upload Memory Size Settings
DATA_UPLOAD_MAX_MEMORY_SIZE = 200 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 200 * 1024 * 1024


FRONTEND_URL = os.getenv("FRONTEND_URL")



EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').strip().lower() in ('true', '1', 'yes')
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'False').strip().lower() in ('true', '1', 'yes')
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'no-reply@remyza.com')


TWILIO_SMS_WEBHOOK_URL = "https://api.remyza.com/api/v1/twilio/webhook/"
TWILIO_VOICE_WEBHOOK_URL = "https://api.remyza.com/api/v1/twilio/voice/"


SENTDM_API_BASE = os.getenv("SENTDM_API_BASE", "https://api.sent.dm/v3")
SENTDM_API_KEY = os.getenv("SENTDM_API_KEY", "")
SENTDM_ORGANIZATION_ID = os.getenv("SENTDM_ORGANIZATION_ID", "")
SENTDM_SANDBOX_MODE = os.getenv("SENTDM_SANDBOX_MODE", "True").strip().lower() in ("true", "1", "yes")
SENTDM_WEBHOOK_SECRET = os.getenv("SENTDM_WEBHOOK_SECRET", "")
SENTDM_WEBHOOK_TOLERANCE_SECONDS = int(os.getenv("SENTDM_WEBHOOK_TOLERANCE_SECONDS", "300"))
