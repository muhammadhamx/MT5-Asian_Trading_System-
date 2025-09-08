"""
WSGI config for mt5_drf_project project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
from threading import Thread

from django.core.wsgi import get_wsgi_application

from mt5_integration.auto_trade_mode import auto_trade_main_loop, ENABLE_AUTO_TRADING

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mt5_drf_project.settings')

if ENABLE_AUTO_TRADING:
    auto_thread = Thread(target=auto_trade_main_loop, daemon=True)
    auto_thread.start()
    print("[AutoTrade] Auto mode is running alongside Django server.")

application = get_wsgi_application()
