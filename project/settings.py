# settings.py (The Final, Correct, and Unified Version)

import os
from pathlib import Path
from datetime import timedelta
import smtplib
from decouple import config
import dj_database_url
from dotenv import load_dotenv
from celery.schedules import crontab
import ssl



# Load environment variables from .env file
load_dotenv()

SUGGESTION_PERIOD_DAYS = 1 

# ==============================================================================
# CORE PATHS & SECURITY
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = config('SECRET_KEY', default='django-insecure-^y=9!qt$+ya-qg9_(#sa!)j%_@bl*uxe8(4(w9%ycs@b&vb*mg')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = ['*'] # In production, restrict this to your domain
ROOT_URLCONF = 'project.urls'
WSGI_APPLICATION = 'project.wsgi.application'
ASGI_APPLICATION = 'project.asgi.application'
AUTH_USER_MODEL = 'user.User'

# ==============================================================================
# STATIC & MEDIA FILES
# ==============================================================================
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
STATICFILES_STORAGE = 'cloudinary_storage.storage.StaticCloudinaryStorage'
STATIC_ROOT = BASE_DIR / "staticfiles" # For collectstatic
STATIC_URL = "/static/"
MEDIA_URL = '/media/'

# This is the magic switch. It tells any FileField or ImageField
# to use Cloudinary for storage.


# --- CLOUDINARY CONFIGURATION ---
# The CLOUDINARY_URL environment variable contains all your credentials.
# This will be read automatically by the cloudinary_storage library.
# You can optionally set specific configurations here if needed.
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': config('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': config('CLOUDINARY_API_KEY'),
    'API_SECRET': config('CLOUDINARY_API_SECRET'),
}


# ==============================================================================
# CELERY CONFIGURATION
# ==============================================================================

# We will re-use the REDIS_URL from your environment, but point to a different
# logical database to keep things separate from Channels.
# Let's use database 1 for Celery.
# We append '/1' to the Redis URL.
# ======================================================================
# CELERY CONFIGURATION (RENDER TLS SAFE)
# ======================================================================


REDIS_URL = config("REDIS_URL", default="redis://localhost:6379", cast=str)

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL

if CELERY_BROKER_URL.startswith("rediss://"):
    CELERY_BROKER_USE_SSL = {
        "ssl_cert_reqs": ssl.CERT_NONE,
    }

    CELERY_REDIS_BACKEND_USE_SSL = {
        "ssl_cert_reqs": ssl.CERT_NONE,
    }

CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_RESULT_EXTENDED = True
CELERY_TASK_TRACK_STARTED = True




# ==============================================================================
# INSTALLED APPLICATIONS
# ==============================================================================
INSTALLED_APPS = [
    "subscriptions",
    'daphne',
    'channels',
    'chatbot',
    'corsheaders',
    "admin_interface",
    "colorfield",
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    
    # ADD CLOUDINARY'S STATICFILES_STORAGE FIRST FOR TEMPLATE TAGS
    'cloudinary_storage',
    'cloudinary', # ADD THE CORE CLOUDINARY A
    
    'django.contrib.staticfiles',

    # Third-party Core
    
    'rest_framework.authtoken', # <--- ADD THIS LINE BACK, TEMPORARILY
    'rest_framework',
    'rest_framework_simplejwt', # The ONLY token system we will use
    'django_filters',
    'rest_framework_simplejwt.token_blacklist', # <-- ADD THIS LINE
    


    # Allauth & dj-rest-auth
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'dj_rest_auth',
    'dj_rest_auth.registration',

    # Social Providers
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.facebook',

    # Your Apps
    'user.apps.UserConfig',
    'userProfile.apps.UserProfileConfig',
    'userFood.apps.UserFoodConfig',
    'owner.apps.OwnerConfig',
    'nutritionist.apps.NutritionistConfig',
    'features.apps.FeaturesConfig',
    'diet.apps.DietConfig',
    'appointments',
]

# ==============================================================================
# MIDDLEWARE
# ==============================================================================
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware', 
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

# ==============================================================================
# TEMPLATES, DATABASES & CHANNELS
# ==============================================================================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [], 'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request', 'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]
DATABASES = {
    "default": dj_database_url.config(
        default=os.environ.get("DATABASE_URL"),
        conn_max_age=600,
        ssl_require=not DEBUG,  # Enforce SSL in production, not locally
    )
}
# CHANNEL_LAYERS = {
#     "default": {
#         "BACKEND": "channels_redis.core.RedisChannelLayer",
#         "CONFIG": {"hosts": [config("REDIS_URL", default='redis://localhost:6379')]},
#     },
# }
_REDIS_URL = config("REDIS_URL", default='redis://localhost:6379')

if _REDIS_URL.startswith("rediss://"):
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [
                    {
                        "address": _REDIS_URL,
                        "ssl_cert_reqs": None,
                    }
                ],
            },
        },
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [_REDIS_URL],
            },
        },
    }

# ==============================================================================
# CORS & EMAIL SETTINGS
# ==============================================================================
CORS_ALLOWED_ORIGINS = ["http://localhost:5173","https://trackeats-1.onrender.com","https://trackeats.onrender.com", "https://track-eats.onrender.com","https://trackeats-qfl8.onrender.com","https://trackintake-backend.onrender.com","https://trackintake.onrender.com","https://trackintake.co.in"]
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = ["https://track-eats.onrender.com","https://trackeats.onrender.com", "https://trackeats-1.onrender.com", "http://localhost:5173","https://trackeats-qfl8.onrender.com","https://trackintake-backend.onrender.com","https://trackintake.onrender.com","https://trackintake.co.in"]
# ==============================
# RESEND SMTP CONFIG
# ==============================
# EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.resend.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False

EMAIL_HOST_USER = "resend"
EMAIL_HOST_PASSWORD = os.getenv("RESEND_API_KEY")
DEFAULT_FROM_EMAIL = "TrackEats <no-reply@trackintake.co.in>"


# ADD THIS BLOCK:
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',  # <-- THIS IS THE KEY
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# ==============================================================================
# API, JWT, & AUTHENTICATION SETTINGS
# ==============================================================================

# --- Django REST Framework ---
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'project.authentication.FinalJWTAuthentication',
        'rest_framework.authentication.SessionAuthentication', # For browsable API
    ),
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticated',),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
}

# --- Simple JWT ---
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=7),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'BLACKLIST_AFTER_ROTATION': True,
    # This points to your serializer that adds user details to the standard login response
    'TOKEN_OBTAIN_SERIALIZER': 'user.serializers.MyTokenObtainPairSerializer',
}

# --- Allauth & dj-rest-auth (UNIFIED CONFIGURATION) ---
SITE_ID = 1
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Master switch to tell dj-rest-auth to use JWT.
REST_USE_JWT = True
JWT_AUTH_COOKIE = None # We use Authorization headers, not cookies.
JWT_AUTH_REFRESH_COOKIE = None

# This is the single, unified configuration dictionary for dj-rest-auth
REST_AUTH = {
    # This tells dj-rest-auth we are NOT using the old Token model.
    'TOKEN_MODEL': None,
    # This tells dj-rest-auth to use your UserDetailSerializer for rich responses.
    'USER_DETAILS_SERIALIZER': 'user.serializers.UserDetailSerializer',
    # This correctly points to your RegisterSerializer for standard signup.
    'REGISTER_SERIALIZER': 'user.serializers.RegisterSerializer',
}

# Your custom adapter for populating `full_name` on social signup.
SOCIALACCOUNT_ADAPTER = 'user.adapters.CustomSocialAccountAdapter'

# Allauth core behavior settings    
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_USER_MODEL_USERNAME_FIELD = None # CRITICAL: Tells allauth you don't use 'username'.
ACCOUNT_EMAIL_VERIFICATION = 'optional' # Change to 'mandatory' for production.

# Defines behavior for social providers. Credentials are set in the Django Admin.
SOCIALACCOUNT_PROVIDERS = {
    'google': {'SCOPE': ['profile', 'email'], 'AUTH_PARAMS': {'access_type': 'online'}},
    'facebook': {
        'METHOD': 'oauth2', 'SCOPE': ['email', 'public_profile'],
        'FIELDS': ['id', 'email', 'name', 'first_name', 'last_name'], 'EXCHANGE_TOKEN': True,
    }
}

# ==============================================================================
# OTHER PROJECT SETTINGS
# ==============================================================================
GEMINI_API_KEY = config("GEMINI_API_KEY", default=None)
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LANGUAGE_CODE, TIME_ZONE, USE_I18N, USE_TZ = 'en-us', 'UTC', True, True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


CELERY_BEAT_SCHEDULE = {
    'send-appointment-email-reminders-every-minute': {
        'task': 'appointments.tasks.send_appointment_reminders',
        'schedule': crontab(minute='*'),
    },
}
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")
