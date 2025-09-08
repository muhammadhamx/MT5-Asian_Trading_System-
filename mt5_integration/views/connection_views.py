from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from ..services.mt5_service import MT5Service

mt5_service = MT5Service()
from ..serializers import MT5ConnectionSerializer, AccountInfoSerializer
from ..utils.production_logger import api_logger

@csrf_exempt
@api_view(['POST'])
def connect_mt5(request):
    """Connect to MT5 terminal"""
    try:
        serializer = MT5ConnectionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        if mt5_service.connect():
            response = {
                'status': 'success',
                'message': 'Successfully connected to MT5'
            }
            api_logger.log_structured('INFO', 'MT5_CONNECT', response, "MT5 connection successful")
            return JsonResponse(response)
        else:
            response = {
                'status': 'error',
                'message': 'Failed to connect to MT5'
            }
            api_logger.log_structured('ERROR', 'MT5_CONNECT', response, "MT5 connection failed")
            return JsonResponse(response, status=500)
            
    except Exception as e:
        response = {
            'status': 'error',
            'message': str(e)
        }
        api_logger.log_structured('ERROR', 'MT5_CONNECT', response, f"MT5 connection error: {str(e)}")
        return JsonResponse(response, status=500)

@csrf_exempt
@api_view(['POST'])
def disconnect_mt5(request):
    """Disconnect from MT5 terminal"""
    try:
        mt5_service.disconnect()
        response = {
            'status': 'success',
            'message': 'Successfully disconnected from MT5'
        }
        api_logger.log_structured('INFO', 'MT5_DISCONNECT', response, "MT5 disconnection successful")
        return JsonResponse(response)
    except Exception as e:
        response = {
            'status': 'error',
            'message': str(e)
        }
        api_logger.log_structured('ERROR', 'MT5_DISCONNECT', response, f"MT5 disconnection error: {str(e)}")
        return JsonResponse(response, status=500)

@api_view(['GET'])
def get_connection_status(request):
    """Get MT5 connection status"""
    try:
        is_connected = mt5_service.is_connected()
        response = {
            'status': 'success',
            'connected': is_connected,
            'message': 'Connected to MT5' if is_connected else 'Not connected to MT5'
        }
        return JsonResponse(response)
    except Exception as e:
        response = {
            'status': 'error',
            'message': str(e)
        }
        return JsonResponse(response, status=500)

@api_view(['GET'])
def get_account_info(request):
    """Get MT5 account information"""
    try:
        account_info = mt5_service.get_account_info()
        if account_info:
            serializer = AccountInfoSerializer(account_info)
            return Response(serializer.data)
        else:
            return Response(
                {'error': 'Failed to get account info'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
