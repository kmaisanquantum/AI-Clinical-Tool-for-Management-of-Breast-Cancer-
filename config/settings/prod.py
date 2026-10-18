from .base import *
from .base import env

DEBUG = False
ALLOWED_HOSTS = [h for h in env("DJANGO_ALLOWED_HOSTS", "*").split(",") if h]

# HTTPS redirect is enforced at the edge (Coolify/Traefik) and by SECURE_PROXY_SSL_HEADER
# for proxied requests. Keep it on by default, but exempt the liveness probe so an
# in-container or plain-HTTP health check still gets a 200 instead of a 301.
# Set DJANGO_SECURE_SSL_REDIRECT=0 only if the platform probes the container over
# plain HTTP without sending X-Forwarded-Proto.
SECURE_SSL_REDIRECT = env("DJANGO_SECURE_SSL_REDIRECT", "1") == "1"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")  # set only behind trusted Nginx
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/?$"]  # never redirect the internal liveness probe
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
CSRF_TRUSTED_ORIGINS = [o for o in env("CSRF_TRUSTED_ORIGINS", "").split(",") if o]
