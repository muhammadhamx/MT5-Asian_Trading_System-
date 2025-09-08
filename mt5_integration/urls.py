from django.urls import path
from .views import (
    connect_mt5, disconnect_mt5, get_account_info, get_connection_status,
    get_symbols, get_rates, get_current_price, get_open_orders, get_positions
)

urlpatterns = [
    # Connection endpoints
    path('connect/', connect_mt5, name='connect-mt5'),
    path('disconnect/', disconnect_mt5, name='disconnect-mt5'),
    path('connection-status/', get_connection_status, name='connection-status'),
    path('account-info/', get_account_info, name='account-info'),

    # Data endpoints
    path('symbols/', get_symbols, name='symbols'),
    path('rates/', get_rates, name='rates'),
    path('current-price/', get_current_price, name='current-price'),
    path('open-orders/', get_open_orders, name='open-orders'),
    path('positions/', get_positions, name='positions'),

]