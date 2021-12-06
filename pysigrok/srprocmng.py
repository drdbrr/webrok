import asyncio
from subprocess import Popen
from .srtypes import SrDeviceState, SrBlankState
from uuid import uuid4
from os.path import exists as pth_exists
import json
import shortuuid
import io
from struct import unpack
from itertools import count
from logging import getLogger
from tempfile import TemporaryDirectory

#import numpy as np

#import concurrent.futures

#from rdp import rdp
#from crdp import rdp
#from scipy.interpolate import Rbf
#from scipy.optimize import curve_fit
#from scipy import signal

__all__ = [
    "srMng",
    "SrProtocol",
]

JSON_PT = 0b00000001
BINARY_PT = 0b00000010
AUTO_JSON_PT = 0b00000011
AUTO_BINARY_PT = 0b00000100

logger = getLogger('sr-log')

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
        
PA_LEN = 4
    
class SrProtocol(asyncio.Protocol):
    _n = count(0)
    def __init__(self, id, sr_proc):
        
        self._id = id
        self._name = 'session' + str(next(self._n))
        
        self.sr_proc = sr_proc
        self.sr_task = None
        
        self.ws_clients = []
        
        self._clients = {}
        
        self.active_ws = None
        
        self.transport = None
        self.request_queue = {}
        
        self.data_buffer = b''
        self.json_len = None
        self.jsonheader = None
        self.resp_queue = asyncio.Queue(maxsize=1000)
        
        self.contlen = 0
        self.zbuf = b''
        
        self.channels = None
        self._state = SrBlankState(self._id, self._name, '')
        
        
        self._clients = {}
    
    @property
    def sid(self):
        return self._id
    
    @sid.setter
    def sid(self):
        pass
        
        
    def connection_made(self, transport):
        loop = asyncio.get_event_loop()
        self.parser = loop.create_task(self.parser_task())
        self.transport = transport
        
    def _json_decode(self, json_bytes, encoding):
        tiow = io.TextIOWrapper(io.BytesIO(json_bytes), encoding=encoding, newline="")
        obj = json.load(tiow)
        tiow.close()
        return obj
    
    async def process_json(self):
        
        if self.jsonheader['content-type'] == 'text/json':
            rid = self.jsonheader.pop('rid')
            self.request_queue[rid]['data'] = self.jsonheader
            self.request_queue[rid]['ev'].set()
            self.json_len = None
            self.jsonheader = None
            
            #print("text/json")
            
        elif self.jsonheader['content-type'] == 'application/json':
            if "run_session" in self.jsonheader.keys():
                data = self.jsonheader['run_session']
                await self.active_ws.send_json({ 'type':'config', 'sessionRun':data }) #ATTENTION
                
            self.json_len = None
            self.jsonheader = None
            #print('application/json')
            
        elif self.jsonheader['content-type'] == 'application/zip':
            self.contlen = self.jsonheader['content-length']
            contlen = min(self.contlen, len(self.data_buffer))
            self.zbuf += self.data_buffer[:contlen]
            self.contlen -= contlen
            self.data_buffer = self.data_buffer[contlen:]
            
            if not self.contlen:
                self.ws_client.put_analog_data(self.zbuf)
                self.zbuf = b''
                self.json_len = None
                self.jsonheader = None
            #print("application/zip")
        
    async def process_jsonheader(self):
        hdrlen = self.json_len
        if len(self.data_buffer) >= hdrlen:
            self.jsonheader = self._json_decode(self.data_buffer[:hdrlen], "utf-8")
            self.data_buffer = self.data_buffer[hdrlen:]
            await self.process_json()

    def data_received(self, data):
        self.resp_queue.put_nowait(data)

    def connection_lost(self, exc):
        print('Connection lost')
        #self.on_con_lost.set_result(True)
        
    async def req_send(self, req):
        rid = shortuuid.uuid()
        req.update({'rid': rid})
        msg = json.dumps(req)
        msg = len(msg).to_bytes(4, byteorder='little') + msg.encode()
        self.transport.write(msg)
        
        #print("CLI-TX:", msg) #ATTENTION
        
        ev = asyncio.Event()
        self.request_queue.update( {rid : {'ev': ev, 'data': None}} )
        await ev.wait()
        data = self.request_queue[rid].get('data')
        del self.request_queue[rid]
        #print(data)
        return data
    
    async def parser_task(self):
        while True:
            self.data_buffer += await self.resp_queue.get()
            #print("RESP LEN:", len(self.data_buffer), ", CONTLEN:", self.contlen, " json_len:", self.json_len)
            
            while (len(self.data_buffer) > 0):
                if self.contlen > 0:
                    contlen = min(self.contlen, len(self.data_buffer))
                    self.zbuf += self.data_buffer[:contlen]
                    self.contlen -= contlen
                    self.data_buffer = self.data_buffer[contlen:]
                    if not self.contlen:
                        self.ws_client.put_analog_data(self.zbuf)
                        self.zbuf = b''
                        self.json_len = None
                        self.jsonheader = None
                
                if not self.json_len and len(self.data_buffer) >= PA_LEN:# is None:
                    self.json_len = unpack("<L", self.data_buffer[:PA_LEN])[0]
                    self.data_buffer = self.data_buffer[PA_LEN:]
                        
                if self.json_len and self.jsonheader is None :
                    #if self.jsonheader is None:
                    await self.process_jsonheader()

    #--------------------------------------API START--------------------------------------
    
    async def get_run_state(self):
        if isinstance(self._state, SrDeviceState):
            data = await self.req_send({'get':['session_state']})
            return data['get']['session_state']
        else:
            return None
    
    async def set_run_state(self, run):
        
        if run:
            self.send_options()
        
        data = await self.req_send({'set':{'run_session':run}})
        return data['set']['run_session']
    
    
    def send_options(self):
        pass
    
    async def set_channels_params(self, params):
        data = self._state.set_channels_params(params)
        return data
        
    async def set_option(self, opt, value):
        data = self._state.set_option(opt, value)
        return data
    
    async def get_decoders_list(self):
        data = await self.req_send({'get':['decoders_list']})
        decoders = data['get']['decoders_list']
        #print("DECODERS:", decoders)
        return decoders
    
    #async def get_channels(self):
        #print("get_channels------------>", self._state.channels.get())
        #return [] #self._state.get_channels()
    
    #async def get_drivers(self):
        #data = await self.req_send({'get':['drivers']})
        #return data['get']['drivers']
        
    @property
    def session_state(self):
        return self._state.get()
    
    @session_state.setter
    def session_state(self, _):
        pass
    
    async def select_device(self, devNum):
        data = await self.req_send({'set':{'dev_num':devNum}})
        if data['set']['dev_num'] == 'error':
            return {}
        else:
            ses = data['set']['dev_num']
            self._state = SrDeviceState(id = self._id, name = self._name, sourcename = ses['sourcename'], drvopts = ses['drvopts'], devopts = ses['devopts'], channels = ses['channels'])
            return self._state.get()
    
    async def scan_devices(self, drv):
        req = await self.req_send({'set':{'driver':drv}})
        if req['set']['driver'] == 'set':
            data = await self.req_send({'get':['scan']})
            return data['get']['scan']
        else:
            return []
    
    def get_options(self, opts):
        devopts = self._state.devopts.get()
        data = [ item for item in devopts.values() if item['key'] in opts ]
        return  data
    
    def init_client(self, cid):
        new_cid = str(uuid4())
        if cid in self._clients:
            self._clients.update({ new_cid: self._clients[cid] })
        elif not self._clients:
            self._clients.update({new_cid: SrBlankState(new_cid, 'ww') })
        elif cid not in self._clients:
            self._clients.update({ new_cid: list(self._clients.values())[0] })
        return new_cid
        
            
    #TODO
    async def register_pd(self, pdId):
        data = await self.req_send({'set':{'register_pd': pdId}})
        data = data['set']
        return data['register_pd']
        
    def stop(self):
        self.parser.cancel()
        
        #self.writer.close()
        self.transport.close()
        self.sr_proc.kill()
        #self.sr_task.cancel()
        #os.remove(TMP_DIR + self._id + ".sock")
    
    def __del__(self):
        print("Stopping session:", self._id)
        #self.stop()
        
#-------------------------------------
        

class SrProcessManager:
    def __init__(self):
        self._procs = {}
        self._tmp_dir = TemporaryDirectory()
        
    def get_sessions(self) -> list:
        return [ item.session_state for item in self._procs.values() ]
        
    async def create_proc(self) -> SrProtocol:
        logger.info(f"{bcolors.WARNING}Create SR session{bcolors.ENDC}")
        loop = asyncio.get_event_loop()
        sid = str(uuid4())
        pth = self._tmp_dir.name + '/' + sid + ".sock"
        sr_proc = Popen(["/home/drjacka/fastapi/webrok/sigrok-proc/src/srproc", "-u", pth])

        while not pth_exists(pth):
            await asyncio.sleep(0)
            
        transport, srProto = await loop.create_unix_connection(lambda: SrProtocol(sid, sr_proc), pth)
        self._procs[sid] = srProto
        return self._procs[sid] #srProto.session_state
    
    def remove_session(self, sid: str):
        logger.info(f"{bcolors.WARNING}Delete SR session{bcolors.ENDC}")
        proc = self._procs[sid]
        proc.stop()
        del self._procs[sid]
        return sid
    
    def get_proc(self, sid: str = None) -> SrProtocol:
        return self._procs.get(sid, list(self._procs.values())[0] )
    
    def sid_exists(self, sid: str) -> bool:
        return sid in self._procs
        
    async def new_session(self):
        proc = await self.create_proc()
        return proc.session_state
        
srMng = SrProcessManager()
