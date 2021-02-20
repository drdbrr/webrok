from multiprocessing import Process, Pipe, Queue, Value
import numpy as np
import asyncio
from collections import deque
from fastapi.logger import logger
from uuid import uuid4
from subprocess import Popen
import zipfile, configparser, time, json, os
import shortuuid

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

class TestWsHandler:
    def __init__(self, ws):
        self.ws = ws
    
    async def send(self, data):
        await self.ws.send_json(data)
    
class SrProcessConnection:
    def __init__(self, id, name):
        self.id = id
        self.name = name #Session name
        self.sr_proc = Popen(["/home/drjacka/fastapi/webrok/sigrok-proc/src/srproc", "-u", tmp_dir + self.id + ".sock"])
        self.sr_task = None
        self.writer = None
        self.reader = None
        self.session_state = None
        self.request_queue = {}
        
        self.ws_client = None
        self.ws_clients = dict()
        
    async def sr_conn_task(self):
        self.reader, self.writer = await asyncio.open_unix_connection(tmp_dir + self.id + ".sock")
        while True:
            response = await self.reader.read(4096)
            #print('SRV-RX:', response)
            if response:
                if response[0] == JSON_PT:
                    data = json.loads(response[1:])
                    rid = data.pop('rid')
                    ev = self.request_queue[rid]['ev']
                    self.request_queue[rid]['data'] = data
                    ev.set()
                    
                elif response[0] == AUTO_JSON_PT:
                    data = json.loads(response[1:])
                    
                    if "run_session" in data.keys():
                        self.session_state = data['run_session']
                        for client in self.ws_clients.values():
                            #await client.send({ 'type':'config', 'sessionRun':self.session_state })
                            await client.ws.send_json({ 'type':'config', 'sessionRun':self.session_state })
                    
                elif response[0] == AUTO_BINARY_PT:
                    print('RX data:', response)
            else:
                break

    async def req_send(self, req):
        rid = shortuuid.uuid()
        req.update({'rid': rid})
        msg = json.dumps(req)
        self.writer.write(msg.encode())
        await self.writer.drain()
        ev = asyncio.Event()
        self.request_queue.update( { rid : {}} )
        self.request_queue[rid]['ev'] = ev
        self.request_queue[rid]['data'] = None
        await ev.wait()
        data = self.request_queue[rid].get('data')
        del self.request_queue[rid]
        return data
    
    async def update_session_state(self):
        data = await self.req_send({'get':['session_state']})
        self.session_state = int(data['get']['session_state'])
        
        for client in self.ws_clients.values():
            await client.ws.send_json({ 'type':'config', 'sessionRun':self.session_state })
    
    async def get_channels(self):
        data = await self.req_send({'get':['channels']})
        col_num = 0
        for chg in data['get']['channels'].values():
            for ch in chg:
                ch['color'] = colorsArray[col_num]
                col_num += 1
        return data['get']['channels']
            
    async def get_sample(self):
        data = await self.req_send({'get':['sample', 'samples']})
        return data['get']
            
    async def get_samplerate(self):
        data = await self.req_send({'get':['samplerate', 'samplerates']})
        return data['get']
            
    async def get_drivers(self):
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
    
    async def run_session(self):
        data = await self.req_send({'set':{'run_session':int(self.session_state)}})
        self.session_state = data['set']['run_session']
        
        for client in self.ws_clients.values():
            await client.ws.send_json({ 'type':'config', 'sessionRun':self.session_state })
        
    def stop(self):
        self.sr_proc.kill()
        self.writer.close()
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

    def get_drivers(self):
        id = next(iter(self._procs))
        proc = self._procs[id]
        drv_list = proc.get_drivers()
        return drv_list
        
    def get_sessions(self):
        return [ { 'id':item, 'name':self._procs[item].name } for item in self._procs ]
        
    async def create_session(self):
        logger.info(f"{bcolors.WARNING}Create SR session{bcolors.ENDC}")
        name = 'session' + str(self.ses_num)
        id = str(uuid4())
        proc = SrProcessConnection(id, name)
        self.ses_num += 1
        
        self._procs[id] = proc
        while not os.path.exists(tmp_dir + id + ".sock"):
            await asyncio.sleep(0)
            
        proc.sr_task = self.loop.create_task(proc.sr_conn_task())
        
        return { 'id':id, 'name': proc.name }
    
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
        
