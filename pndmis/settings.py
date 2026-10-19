import os
from pathlib import Path
BASE_DIR=Path(__file__).resolve().parent.parent
env_file = BASE_DIR / '.env'
if env_file.exists():
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())
SECRET_KEY=os.environ.get('DJANGO_SECRET_KEY','')
if not SECRET_KEY: raise RuntimeError('DJANGO_SECRET_KEY is required')
DEBUG=os.environ.get('DJANGO_DEBUG','False')=='True'
ALLOWED_HOSTS=[x for x in os.environ.get('DJANGO_ALLOWED_HOSTS','').split(',') if x]
CSRF_TRUSTED_ORIGINS=[x for x in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS','').split(',') if x]
INSTALLED_APPS=['django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles','core']
MIDDLEWARE=['django.middleware.security.SecurityMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF='pndmis.urls'
TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.debug','django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION='pndmis.wsgi.application'
# Local development only. Use an approved managed PostgreSQL service for deployment.
DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':BASE_DIR/'local_dev.sqlite3'}}
AUTH_PASSWORD_VALIDATORS=[{'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator','OPTIONS':{'min_length':12}},{'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},{'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'}]
LANGUAGE_CODE='en-us'; TIME_ZONE='Asia/Manila'; USE_I18N=True; USE_TZ=True
STATIC_URL='static/'; DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
LOGIN_URL='login'; LOGIN_REDIRECT_URL='dashboard'; LOGOUT_REDIRECT_URL='login'
SESSION_COOKIE_HTTPONLY=True; SESSION_COOKIE_SECURE=not DEBUG; CSRF_COOKIE_SECURE=not DEBUG
SECURE_SSL_REDIRECT=not DEBUG; SECURE_HSTS_SECONDS=31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS=not DEBUG; SECURE_CONTENT_TYPE_NOSNIFF=True
X_FRAME_OPTIONS='DENY'; SECURE_REFERRER_POLICY='same-origin'
