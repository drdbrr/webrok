from multiprocessing import Process, Pipe, Queue, Value
import numpy as np
import asyncio
from collections import deque
from fastapi.logger import logger
from uuid import uuid4
from subprocess import Popen
import configparser, time, json, os, zlib
import numpy as np
import shortuuid
import io
import operator
import struct
import concurrent.futures

#from rdp import rdp
#from crdp import rdp
#from scipy.interpolate import Rbf
from scipy.optimize import curve_fit
from scipy import signal

import statistics

tmp_dir = '/tmp/webrok/'

JSON_PT = 0b00000001
BINARY_PT = 0b00000010
AUTO_JSON_PT = 0b00000011
AUTO_BINARY_PT = 0b00000100

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    
colorsArray = [
    '#fce94f', '#fcaf3e', '#e9b96e', '#8ae234', '#729fcf', '#ad7fa8', '#cf72c3', '#ef2929',
    '#edd400', '#f57900', '#c17d11', '#73d216', '#3465a4', '#75507b', '#a33496', '#cc0000',
    '#c4a000', '#ce5c00', '#8f5902', '#4e9a06', '#204a87', '#5c3566', '#87207a', '#a40000',
    '#16191a', '#2e3436', '#555753', '#888a8f', '#babdb6', '#d3d7cf', '#eeeeec', '#ffffff'
]

class WsHandler:
    def __init__(self, ws, proc):
        self.ws = ws
        self.proc = proc
        self.loop = asyncio.get_event_loop()
        self.task = self.loop.create_task(self.data_task())
        self.mesh_width = 1
        self.zarray = deque()
        self.has_data = 0
        
        self.mesh_data = {}
        
        self.pos = 0
        
        self.zarray_indx = 0
        
        self.scale = None
        
    def init_a(self):
        for ch in self.proc.channels['analog']:
            for ch in self.proc.channels['analog']:
                if ch['visible'] is True:
                    self.mesh_data.update({ch['name']: {'data':[], 'range':[0, 0], 'pos':0}})
                    
    def freduce(self, data, step):
        dq = deque()
        for i in range(0, data.size, step):
            mn = min(data[i : i + step])
            mx = max(data[i : i + step])
            dq.extend([mn, mx])
        
        return np.asarray(list(dq), dtype=np.float32)
                    
    #def test(self):
        #mesh_data = self.mesh_data
        #rdata = zlib.decompress(self.zarray[0])
        #fdata = np.frombuffer(rdata, dtype=np.float32)
        
        #fdata = np.reshape(fdata, (5, -1))
        
        #for i, ch in enumerate(mesh_data):
            #fsdata = fdata[i]
            #fslice = fsdata[0:8000]
            #fslice = np.reshape(fslice, (fslice.size, 1))
            #x = np.arange(0, fslice.size, dtype=np.float32).reshape(fslice.size, 1)
            #fslice = np.concatenate((x, fslice), axis=1)
            #tmp = np.empty((0,2), np.float32)
            
            #step = 8
            #for i in range(0, 8000, step):
                #v = rdp(fslice[i: i + step], epsilon=1)
                #tmp = np.append(tmp, v, axis=0)
            
            #z = np.zeros((int(tmp.size/2), 1), dtype=np.float32)
            #odata = np.concatenate((tmp, z), axis=1).flatten()
            #mesh_data.update({ch : {'data':odata.tolist(), 'range':[0, int(fdata.size / 5)], 'pos':0}})
            #self.mesh_width += fdata.size / 5
            #print('========== ch:', ch, ' len:', len(mesh_data[ch]['data'])/3)#len(mesh_data['A0']['data']))
        
        #return mesh_data
        
    def func(self, x, a, b, c):
        return a * np.exp(-b * x) + c
        
    def test(self):
        mesh_data = self.mesh_data
        rdata = zlib.decompress(self.zarray[0])
        fdata = np.frombuffer(rdata, dtype=np.float32)
        
        fdata = np.reshape(fdata, (5, -1))
        
        for i, ch in enumerate(mesh_data):
            fsdata = fdata[i]
            fslice = fsdata[0:8000]
            
            y = signal.resample(fslice, 4000)
            x = np.arange(0, int(y.size * 2), 2, dtype=np.float32)
            z = np.zeros((int(y.size)), dtype=np.float32)
            
            x = x.reshape(y.size, 1)
            y = y.reshape(y.size, 1)
            z = z.reshape(y.size, 1)
            
            odata = np.concatenate((x, y, z), axis=1).flatten()
            
            mesh_data.update({ch : {'data':odata.tolist(), 'range':[0, int(fdata.size / 5)], 'pos':0}})
            self.mesh_width += fdata.size / 5
        
        return mesh_data
        
    async def data_task(self):
        loop = asyncio.get_running_loop()
        executor = concurrent.futures.ThreadPoolExecutor()
            
        while True:
            if self.mesh_width < 1680 and self.has_data > 0:
                mesh_data = await loop.run_in_executor(executor, self.test)
                await self.ws.send_json({ 'type':'data', 'data':{'analog':mesh_data} })
                
            await asyncio.sleep(0.01)
        
    def put_analog_data(self, data):
        self.zarray.append(data)
        self.has_data += 1
        print("TOTAL COLLECTOR LEN:", len(self.zarray))
        
    def rst_buff(self):
        self.zarray.clear()
        self.has_data = 0
        
PA_LEN = 4

#class SrState:
    #def __init__(self):
        #self.zarray = collections.deque()
        #self.has_data = 0
        
    #def put_analog_data(self, data):
        #self.zarray.append(data)
        #self.has_data += 1
        
    #def rst_buff(self):
        #self.zarray.clear()
        #self.has_data = 0
        

    

class SrProtocol(asyncio.Protocol):
    def __init__(self, id, name, sr_proc):
        
        self.id = id
        self.name = name
        self.sr_proc = sr_proc
        self.sr_task = None
        self.session_state = None
        
        self.ws_client = None
        self.ws_clients = dict()
        
        
        self.transport = None
        self.request_queue = {}
        
        self.data_buffer = b''
        self.json_len = None
        self.jsonheader = None
        self.resp_queue = asyncio.Queue(maxsize=1000000)
        
        self.contlen = 0
        self.zbuf = b''
        #self.zarray = collections.deque()
        
        #self.srState = SrState()
        
        self.channels = None

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
            
            print("text/json")
            
        elif self.jsonheader['content-type'] == 'application/json':
            if "run_session" in self.jsonheader.keys():
                self.session_state = self.jsonheader['run_session']
                for client in self.ws_clients.values():
                    await client.ws.send_json({ 'type':'config', 'sessionRun':self.session_state })            
            
            self.json_len = None
            self.jsonheader = None
            print('application/json')
            
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
            print("application/zip")
        
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
        
        print("CLI-TX:", msg)
        
        ev = asyncio.Event()
        self.request_queue.update( {rid : {'ev': ev, 'data': None}} )
        await ev.wait()
        data = self.request_queue[rid].get('data')
        del self.request_queue[rid]
        return data
    
    async def parser_task(self):
        while True:
            self.data_buffer += await self.resp_queue.get()
            print("RESP LEN:", len(self.data_buffer), ", CONTLEN:", self.contlen, " json_len:", self.json_len)
            
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
                    self.json_len = struct.unpack("<L", self.data_buffer[:PA_LEN])[0]
                    self.data_buffer = self.data_buffer[PA_LEN:]
                        
                if self.json_len and self.jsonheader is None :
                    #if self.jsonheader is None:
                    await self.process_jsonheader()

    async def update_session_state(self):
        data = await self.req_send({'get':['session_state']})
        self.session_state = int(data['get']['session_state'])
        
        for client in self.ws_clients.values():
            await client.ws.send_json({ 'type':'config', 'sessionRun':self.session_state })
            
            
    async def get_decoders_list(self):
        data = await self.req_send({'get':['decoders_list']})
        decoders = data['get']['decoders_list']
        print("DECODERS:", decoders)
        return decoders
    
    async def get_channels(self):
        data = await self.req_send({'get':['channels']})
        
        channels = data['get']['channels']
        
        if self.channels is None:
            col_num = 0
            self.channels = dict()
            for key in channels.keys():
                self.channels[key] = list()
                for ch in channels[key]:
                    self.channels[key].append({'color':colorsArray[col_num], 'name':ch['name']})
                    col_num += 1
        
        for key in channels.keys():
            [i.update(j) for i, j in zip(sorted(self.channels[key], key=operator.itemgetter("name")), sorted(channels[key], key=operator.itemgetter("name")))]
        
        return  self.channels
            
    async def get_sample(self):
        data = await self.req_send({'get':['sample', 'samples']})
        return data['get']
            
    async def get_samplerate(self):
        data = await self.req_send({'get':['samplerate', 'samplerates']})
        return data['get']
            
    async def get_drivers(self):
        print('GET DRIV')
        data = await self.req_send({'get':['drivers']})
        return data['get']['drivers']
        
    async def get_session(self):
        data = await self.req_send({'get':['session']})
        session = dict(data['get']['session'])
        session.update({'id':self.id, 'name':self.name})
        return session
    
    async def select_device(self, devNum):
        data = await self.req_send({'set':{'dev_num':devNum}})
        if data['set']['dev_num'] == 'set':
            session = await self.get_session()
            return session
        else:
            return {}
    
    async def scan_devices(self, drv):
        req = await self.req_send({'set':{'driver':drv}})
        if req['set']['driver'] == 'set':
            data = await self.req_send({'get':['scan']})
            return data['get']['scan']
        else:
            return []
        
    async def select_sample(self, sample):
        data = await self.req_send({'set':{'sample':int(sample)}})
        return data['set']['sample']
    
    async def select_samplerate(self, samplerate):
        data = await self.req_send({'set':{'samplerate':int(samplerate)}})
        return data['set']['samplerate']
    
    async def run_session(self, run, id):
        if run is True:
            
            self.ws_id = id
            #self.zarray.clear()
            #self.srState.rst_buff()
            
            self.ws_client = self.ws_clients[id]
            
            self.ws_client.rst_buff()
            
        data = await self.req_send({'set':{'run_session':int(self.session_state)}})
        self.session_state = data['set']['run_session']
        
        for client in self.ws_clients.values():
            await client.ws.send_json({ 'type':'config', 'sessionRun':self.session_state })
            
    async def update_channel(self, channel):
        data = await self.req_send({'set':channel})
        data = data['set']
        data.update({'type':'config'})
        for client in self.ws_clients.values():
            await client.ws.send_json(data)
            
    #TODO
    async def register_pd(self, pdId):
        data = await self.req_send({'set':{'register_pd': pdId}})
        print("============>DATA:", data)
        data = data['set']
        return data['register_pd']
        
    def stop(self):
        self.sr_proc.kill()
        #self.writer.close()
        self.transport.close()
        self.sr_task.cancel()
        os.remove(tmp_dir + self.id + ".sock")
    
    def __del__(self):
        print("Stopping session:", self.id)
#_____________________________________

class SrProcessManager:
    def __init__(self):
        self._procs = {}
        self.ses_num = 0
        self.loop = asyncio.get_event_loop()
        
    def get_sessions(self):
        return [ { 'id':item, 'name':self._procs[item].name } for item in self._procs ]
        
    async def create_session(self):
        logger.info(f"{bcolors.WARNING}Create SR session{bcolors.ENDC}")
        name = 'session' + str(self.ses_num)
        id = str(uuid4())
        sr_proc = Popen(["/home/drjacka/fastapi/webrok/sigrok-proc/src/srproc", "-u", tmp_dir + id + ".sock"])
        
        while not os.path.exists(tmp_dir + id + ".sock"):
            await asyncio.sleep(0)
        
        #on_con_lost = self.loop.create_future()
        transport, srProto = await self.loop.create_unix_connection(lambda: SrProtocol(id, name, sr_proc), tmp_dir + id + ".sock")

        self.ses_num += 1
        self._procs[id] = srProto
        return { 'id':id, 'name': srProto.name }
    
    def get_by_id(self, id):
        if id in self._procs:
            return self._procs[id]
        else:
            return None
    
    async def delete_session(self, id):
        logger.info(f"{bcolors.WARNING}Delete SR session{bcolors.ENDC}")
        self._procs[id].stop()
        del self._procs[id]
        return id
        
