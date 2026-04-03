import json
from channels.generic.websocket import AsyncWebsocketConsumer

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Grab the session ID from the WebSocket URL
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.room_group_name = f'chat_{self.session_id}'

        # Join the session group so Celery can find us
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Leave the room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # This method catches messages sent by Celery and pushes them to React
    async def agent_message(self, event):
        message = event['message']
        status = event.get('status', 'update')
        
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'status': status,
            'message': message
        }))