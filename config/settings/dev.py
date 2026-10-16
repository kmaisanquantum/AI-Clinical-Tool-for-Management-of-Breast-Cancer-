from .base import *
from .base import env

DEBUG = env("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = ALLOWED_HOSTS or ["localhost", "127.0.0.1"]
