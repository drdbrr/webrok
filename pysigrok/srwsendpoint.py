from fastapi.logger import logger
from starlette.endpoints import WebSocketEndpoint

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
        self.srmng = None
        
    async def on_connect(self, websocket):
        logger.info(f"{bcolors.WARNING}WS connect{bcolors.ENDC}")
        self.srmng = self.scope.get('srmng')
        await websocket.accept()
        data = await websocket.receive_json()
        id = data['id']
        self.proc = self.srmng.get_by_id(id)
        self.proc.ws_client = websocket
        logger.info(f"{bcolors.WARNING}WS accepted id: %s {bcolors.ENDC}", id)
        
    async def on_receive(self, websocket, data):
        #print('WS data:', data,)
        #logger.debug(f'{bcolors.WARNING}WS data: %s{bcolors.ENDC}', data)
        for key in data.keys():
            if key == 'scale':
                self.proc.update_scale(data.get('scale'))
                
            elif key == 'x':
                self.proc.update_x(data.get('x'))
                
            elif key == 'session_run' and data.get('session_run'):
                await self.proc.start_session(data.get('session_run'))
            
            elif key == 'session_run' and not data.get('session_run'):
                await self.proc.stop_session()
        
    async def on_disconnect(self, websocket, close_code):
        logger.info(f"{bcolors.WARNING}WS disconnect{bcolors.ENDC}") 
