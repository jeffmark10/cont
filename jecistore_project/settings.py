# jecistore_project/settings.py
import os
from pathlib import Path
import environ
import sys

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()

environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

SECRET_KEY = env('DJANGO_SECRET_KEY')

DEBUG = env.bool('DJANGO_DEBUG', default=False)

if DEBUG:
    ALLOWED_HOSTS = ['*']
else:
    allowed_hosts_from_env = env.list('DJANGO_ALLOWED_HOSTS', default=[])
    essential_hosts = ['jecistore.onrender.com', '127.0.0.1', 'localhost']
    ALLOWED_HOSTS = list(set(allowed_hosts_from_env + essential_hosts))

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'store',
    'cloudinary',
    'cloudinary_storage',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # Adicionado WhiteNoise para servir ficheiros estáticos
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'jecistore_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'store.context_processors.cart_items_count',
            ],
        },
    },
]

WSGI_APPLICATION = 'jecistore_project.wsgi.application'

DATABASES = {
    'default': env.db_url('DATABASE_URL')
}

DATABASES['default']['CONN_MAX_AGE'] = 600
DATABASES['default']['OPTIONS'] = {'client_encoding': 'UTF8'}

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

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# ADICIONE ISTO: Onde Django deve procurar arquivos estáticos extras
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'), # Seu diretório static existente, agora incluindo static/dist
]

# Configuração para WhiteNoise
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Cloudinary configuration (moved outside the DEBUG block to be always available)
CLOUDINARY_CLOUD_NAME = env('CLOUDINARY_CLOUD_NAME')
CLOUDINARY_API_KEY = env('CLOUDINARY_API_KEY')
CLOUDINARY_API_SECRET = env('CLOUDINARY_API_SECRET')

# NOVO: Força o Cloudinary a usar HTTPS para todas as URLs geradas
CLOUDINARY_SECURE_DISTRIBUTION = True
CLOUDINARY_SECURE = True

if not DEBUG:
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
    MEDIA_URL = '/media/'
else:
    MEDIA_URL = '/media/'
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'
LOGIN_URL = 'login'

HANDLER404 = 'store.views.custom_404_view'
HANDLER500 = 'store.views.custom_500_view'

STORE_WHATSAPP_NUMBER = env('STORE_WHATSAPP_NUMBER', default='5586981247491')

# Configuração de Logging (NOVO)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO', # Em desenvolvimento, mostre INFO e acima no console
            'class': 'logging.StreamHandler',
            'formatter': 'simple' if DEBUG else 'verbose', # Mais simples em debug
            'stream': sys.stdout, # Envia para stdout, que o Render captura
        },
        'file': {
            'level': 'DEBUG', # Grave tudo (DEBUG e acima) em um arquivo em produção
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'django_debug.log'),
            'maxBytes': 1024 * 1024 * 5, # 5 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'store': { # Logger para o seu aplicativo 'store'
            'handlers': ['console'],
            'level': 'DEBUG', # Nível mais detalhado para seu app em desenvolvimento
            'propagate': False,
        },
        '': { # Logger raiz, para capturar logs de outras libs ou não especificados
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# Em produção, adicione o handler de arquivo e aumente o nível de log do Django
if not DEBUG:
    LOGGING['loggers']['django']['handlers'].append('file')
    LOGGING['loggers']['django']['level'] = 'INFO' # Mantenha INFO para Django em produção
    LOGGING['loggers']['store']['handlers'].append('file')
    LOGGING['loggers']['store']['level'] = 'INFO' # Mude para INFO ou WARNING em produção para seu app
    LOGGING['root']['handlers'].append('file')
    LOGGING['root']['level'] = 'INFO'

# Alerta em produção se DEBUG estiver ativado (apenas para depuração no Render)
if not DEBUG:
    if 'runserver' not in sys.argv:
        pass

# Configuração de Cache (NOVO)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}