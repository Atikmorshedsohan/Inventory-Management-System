"""
ASGI config for inventory_backend project.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_backend.settings')

application = get_asgi_application()
