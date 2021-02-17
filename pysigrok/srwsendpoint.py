from fastapi.logger import logger
from starlette.endpoints import WebSocketEndpoint
from uuid import uuid4
from .srprocmng import TestWsHandler

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
        
    async def on_connect(self, websocket):
        logger.info(f"{bcolors.WARNING}WS connect{bcolors.ENDC}")
        await websocket.accept()
        data = await websocket.receive_json()
        self.proc = self.scope['srmng'].get_by_id(data['id'])
        self.proc.ws_client = websocket
        
        testWsHandler = TestWsHandler(websocket)
        self.proc.ws_clients.update({ str(uuid4()) : testWsHandler })
        
        await self.proc.update_session_state()
        
        logger.info(f"{bcolors.WARNING}WS accepted id: %s {bcolors.ENDC}", id)
        
    async def on_receive(self, websocket, data):
        print('WS data:', data,)
        #logger.debug(f'{bcolors.WARNING}WS data: %s{bcolors.ENDC}', data)
        for key in data.keys():
            if key == 'scale':
                pass
                #self.proc.update_scale(data.get('scale'))
                
            #elif key == 'x':
                #self.proc.update_x(data.get('x'))
                
            elif key == 'session_run':
                await self.proc.run_session()

        
    async def on_disconnect(self, websocket, close_code):
        logger.info(f"{bcolors.WARNING}WS disconnect{bcolors.ENDC}") 
