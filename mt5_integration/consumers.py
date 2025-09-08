import json
from channels.generic.websocket import AsyncWebsocketConsumer

class LogConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = "logs"
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    # Receive message from WebSocket
    async def receive(self, text_data):
        pass
    
    # Receive message from room group
    async def log_message(self, event):
        message = event['message']
        log_type = event.get('log_type', 'info')
        
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': message,
            'type': log_type
        }))