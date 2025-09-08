# mt5_integration/utils.py
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def send_log(message, log_type='info'):
    """
    Send a log message to all connected WebSocket clients or fall back to file logging
    """
    import logging
    import os
    from datetime import datetime
    
    # Configure file logger
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    log_file = os.path.join(log_dir, 'trading.log')
    file_logger = logging.getLogger('file_logger')
    
    if not file_logger.handlers:
        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
        handler.setFormatter(formatter)
        file_logger.addHandler(handler)
        file_logger.setLevel(logging.INFO)
    
    # Log to file
    log_level = getattr(logging, log_type.upper(), logging.INFO)
    file_logger.log(log_level, message)
    
    # Try websocket logging if available
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'logs',
            {
                'type': 'log_message',
                'message': message,
                'log_type': log_type
            }
        )
    except Exception:
        # Already logged to file, no need to handle error
        pass