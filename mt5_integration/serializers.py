from rest_framework import serializers
from django.conf import settings

class MT5ConnectionSerializer(serializers.Serializer):
    """Serializer for MT5 connection parameters"""
    login = serializers.IntegerField(required=False)
    password = serializers.CharField(required=False)
    server = serializers.CharField(required=False)

class AccountInfoSerializer(serializers.Serializer):
    """Serializer for MT5 account information"""
    login = serializers.IntegerField()
    server = serializers.CharField()
    balance = serializers.FloatField()
    equity = serializers.FloatField()
    margin = serializers.FloatField()
    margin_free = serializers.FloatField()
    margin_level = serializers.FloatField()
    currency = serializers.CharField()

class SymbolSerializer(serializers.Serializer):
    """Serializer for MT5 symbol information"""
    name = serializers.CharField()
    description = serializers.CharField()
    base_currency = serializers.CharField()
    quote_currency = serializers.CharField()
    digits = serializers.IntegerField()

class RatesSerializer(serializers.Serializer):
    """Serializer for MT5 rates data"""
    time = serializers.DateTimeField()
    open = serializers.FloatField()
    high = serializers.FloatField()
    low = serializers.FloatField()
    close = serializers.FloatField()
    tick_volume = serializers.IntegerField()
    spread = serializers.IntegerField()
    real_volume = serializers.IntegerField()