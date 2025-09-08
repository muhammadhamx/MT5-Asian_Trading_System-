from django.http import JsonResponse
from rest_framework.decorators import api_view

from ..services.mt5_service import MT5Service

mt5_service = MT5Service()
from ..serializers import SymbolSerializer, RatesSerializer
from ..utils.production_logger import api_logger

@api_view(['GET'])
def get_symbols(request):
    """Get available symbols from MT5"""
    try:
        symbols = mt5_service.get_symbols()
        serializer = SymbolSerializer(symbols, many=True)
        return JsonResponse({
            'status': 'success',
            'symbols': serializer.data
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@api_view(['GET'])
def get_rates(request):
    """Get symbol rates from MT5"""
    try:
        symbol = request.GET.get('symbol', 'XAUUSD')
        timeframe = request.GET.get('timeframe', 'M1')
        count = int(request.GET.get('count', 100))
        
        rates = mt5_service.get_rates(symbol, timeframe, count)
        serializer = RatesSerializer(rates, many=True)
        return JsonResponse({
            'status': 'success',
            'rates': serializer.data
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@api_view(['GET'])
def get_current_price(request):
    """Get current price for a symbol"""
    try:
        symbol = request.GET.get('symbol', 'XAUUSD')
        price = mt5_service.get_current_price(symbol)
        return JsonResponse({
            'status': 'success',
            'symbol': symbol,
            'price': price
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@api_view(['GET'])
def get_open_orders(request):
    """Get open orders from MT5"""
    try:
        orders = mt5_service.get_open_orders()
        return JsonResponse({
            'status': 'success',
            'orders': orders
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@api_view(['GET'])
def get_positions(request):
    """Get open positions from MT5"""
    try:
        positions = mt5_service.get_positions()
        return JsonResponse({
            'status': 'success',
            'positions': positions
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
