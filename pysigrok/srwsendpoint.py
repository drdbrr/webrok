from fastapi.logger import logger
from starlette.endpoints import WebSocketEndpoint
from uuid import uuid4
import asyncio
from collections import deque

from .srprocmng import srMng

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
        self.task = None
        self.x = None
        self.scale = None
        self.data_dst = None
        
        self.state = None
        
    async def on_connect(self, websocket):
        logger.info(f"{bcolors.WARNING}WS connect{bcolors.ENDC}")
        await websocket.accept()
        data = await websocket.receive_json()
        
        self.proc = srMng.get_by_id(data['id'])
        
        self.state = self.proc._state.copy()
        

        
        #await websocket.send_json({ 'type':'config', 'x':self.x, 'scale':self.scale, 'run':data })
        
    async def on_receive(self, websocket, data):
        print('WS RX:', data)
        
        if 'run' in data:
            print("Recv session_run:", data)
            self.proc.active_ws = websocket
            resp = await self.proc.set_run_state(data['run'])
            await websocket.send_json({'type':'config', **resp})
            
        elif 'scale' in data:
            self.scale = data['scale']
            print('scale:', self.scale)
            
        elif 'x' in data:
            self.x = data['x']
            print('x:', self.x)
            
        elif 'cid' in data:
            cid = data['cid']
            del self.proc._clients[cid]
        
    async def on_disconnect(self, websocket, close_code):
        print('WS DISCONNECT')
        logger.info(f"{bcolors.WARNING}WS disconnect{bcolors.ENDC}") 
