from fastapi.logger import logger
from starlette.endpoints import WebSocketEndpoint
from uuid import uuid4
import asyncio
from .srprocmng import WsHandler

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class SrWsEndpoint(WebSocketEndpoint):
    encoding = 'json'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.proc = None
        self.id = str(uuid4())
        self.wsHandler = None
        
    async def on_connect(self, websocket):
        logger.info(f"{bcolors.WARNING}WS connect{bcolors.ENDC}")
        await websocket.accept()
        data = await websocket.receive_json()
        self.proc = self.scope['srmng'].get_by_id(data['id'])
        self.wsHandler = WsHandler(websocket, self.proc)
        self.proc.ws_clients[self.id] = self.wsHandler
        await self.proc.update_session_state()
        
        
    async def on_receive(self, websocket, data):
        #print('WS data:', data)
        if 'session_run' in data:
            self.wsHandler.init_a()
            await self.proc.run_session(data['session_run'], self.id)
        elif 'channel' in data:
            await self.proc.update_channel(data)
            
        elif 'scale' in data:
            scale = data['scale']
            self.wsHandler.mesh_width *= scale
            self.wsHandler.scale = scale
            print('mesh:', self.wsHandler.mesh_width, ' scale:', self.wsHandler.scale)
            
        elif 'x' in data:
            x = data['x']
            self.wsHandler.mesh_width -= x
            print(self.wsHandler.mesh_width)
        
    async def on_disconnect(self, websocket, close_code):
        del self.proc.ws_clients[self.id]
        logger.info(f"{bcolors.WARNING}WS disconnect{bcolors.ENDC}") 
