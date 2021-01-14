from multiprocessing import Process, Pipe, Queue, Value
import numpy as np
import asyncio
from collections import deque
from fastapi.logger import logger
from uuid import uuid4
from .srprocess import SrProcess

import zipfile, configparser, time

tmp_dir = '/tmp/webrok/'

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
            
class SrApi:
    def __init__(self, req, param = None):
        self.cb = req
        self.param = param
        
    def run(self, context):
        func = getattr(context, self.cb)
        if self.param is not None:
            func(self.param)
        else:
            func()

class SrProcessConnection:
    def __init__(self, id, name):
        self.id = id
        self.name = name #Session name
        
        self.client_pipe_A, self.client_pipe_B = Pipe()
        self.ss_flag = Value('h', 0)
        
        self.sigrok = SrProcess(self.client_pipe_B, self.ss_flag, name = self.id, daemon=True)
        self.sigrok.start()
        
        self.ws_client = None
        self.ws_task = None
        self.a_data_task = None
        
        #self.data = {'logic':deque(), 'analog':deque()}

        self._displayWidth = 2000
        self._has_data = 0
        self._x = 0
        self._scale = 1
        self._mesh_width = 1
        #self._camera_pos = 0
        #self._C = None
        self._pckLen = 512
        self._bitWidth = 1 #50 или 1
        self._bitHeight = 1 #50 или 1
        self._positions = list( [0] * 8)
        self._ranges = list( [0] * 8)
        
        self.bt = 0
        
        self._logic_pck_num = 0
        self._analog_pck_num = 0
        self.pl = 0
        self.pckNum = 0
        
        self.channels = None
        self.mesh_logic_data = {}
        self.mesh_analog_data = {}
        self.logic_data = deque()
        self.analog_data = deque()
        
        logger.info(f"{bcolors.WARNING}SR pid: %s{bcolors.ENDC}", self.sigrok.pid)
        
    def get_channels(self):
        data = self.runcmd('get_channels')
        return data
        
    def get_sample(self):
        data = self.runcmd('get_sample')
        return data
        
    def get_samplerate(self):
        data = self.runcmd('get_samplerate')
        return data
        
    def select_samplerate(self, smp):
        res = self.runcmd('set_samplerate', smp)
    
    def select_sample(self, smpl):
        res = self.runcmd('set_sample', smpl)
        
    def scan_devices(self, drv):
        data = self.runcmd('get_scan', drv)
        return data
    
    def get_session(self):
        data = self.runcmd('get_session')
        data['id'] = str(self.id)
        data['name'] = str(self.name)
        return data
    
    async def select_device(self, devNum):
        loop = asyncio.get_event_loop()
        self.channels = self.runcmd('set_device_num', devNum)
        
        self.mesh_logic_data.clear()
        self.mesh_analog_data.clear()
        
        if 'logic' in self.channels.keys():
            self.lreader, wr = await asyncio.open_unix_connection(tmp_dir + self.id + 'lsock')
            self.l_data_task = loop.create_task(self.ldata_handler_task())
            print('Open lsock')
            
        if 'analog' in self.channels.keys():
            self.areader, wr = await asyncio.open_unix_connection(tmp_dir + self.id + 'asock')
            self.a_data_task = loop.create_task(self.adata_handler_task())
            print('Open asock')
            
        for item in self.channels['logic']:
            self.mesh_logic_data.update({item['name']:{'data':[], 'range':[0, 0], 'pos':0}})
            
        for item in self.channels['analog']:
            self.mesh_analog_data.update({item['name']:{'data':[], 'range':[0, 0], 'pos':0}})
            
        data = self.get_session()
        return data
            
    def runcmd(self, cmd, param = None):
        request = SrApi(cmd, param)
        self.client_pipe_A.send(request)
        try:
            data = self.client_pipe_A.recv()
        except:
            print('error reading data')
        return data
#----------------------------------------------
    
    async def start_session(self, run):
        print('Start session data collection')

        #self.data['analog'].clear()
        #self.data['logic'].clear()
        self.logic_data.clear()
        self.analog_data.clear()
        
        self._logic_pck_num = 0
        self._analog_pck_num = 0
        self._mesh_width = 0
        self.pl = 0
        self.pckNum = 0
        self._has_data = 0
        self._positions = list( [0] * 8)
        self._ranges = list( [0] * 8)
        
        
        self.ss_flag.value = 1
        request = SrApi('session_run', True)
        
        self.client_pipe_A.send(request)
        if self.client_pipe_A.poll(0.1):
            resp = self.client_pipe_A.recv()
            await self.ws_client.send_json({ 'type':'config', 'sessionRun':False })
        else:
            self.bt = time.time()
            await self.ws_client.send_json({ 'type':'config', 'sessionRun':True })
            
    async def stop_session(self):
        self.ss_flag.value = 0
        print('RX analog:', self._analog_pck_num)
        print('RX logic:', self._logic_pck_num)
        print('Session time:', time.time() - self.bt)
        await self.ws_client.send_json({ 'type':'config', 'sessionRun':False })
        
    def update_scale(self, scale):
        self._scale = scale
        self._mesh_width *= self._scale
        print('scale:', scale)
        
    def update_x(self, x):
        self._x += x
        self._mesh_width -= x
        print('x:', self._x)
        
    async def ldata_handler_task(self):
        print(f"{bcolors.OKBLUE}Start data_task{bcolors.ENDC}")
        while True:
            data = await self.lreader.read(4096)
            if data:
                arr = np.frombuffer(data, dtype='uint8').reshape((len(data), 1))
                #self.data['logic'].append(arr)
                self.logic_data.append(arr)
                self._logic_pck_num += 1
                self._has_data += 1
                #await self.ws_client.send_json({ 'type':'cnt', 'pck_cnt': self._has_data})
            else:
                break
        
    async def adata_handler_task(self):
        print(f"{bcolors.OKBLUE}Start data_task{bcolors.ENDC}")
        while True:
            data = await self.areader.read(4096)
            if data:
                self.analog_data.append(np.frombuffer(data, dtype='float32'))
                self._analog_pck_num += 1
                #await self.ws_client.send_json({ 'type':'cnt', 'pck_cnt': self._has_data})
            else:
                break
        
    async def ws_task_coro(self):
        #logger.info(f"{bcolors.WARNING}Start ws_task{bcolors.ENDC}")
        print(f"{bcolors.OKBLUE}Start ws_task{bcolors.ENDC}")
        #pckNum = 0
        while True:
            if self.ws_client:
                if self._mesh_width < self._displayWidth and self._has_data:
                    
                    mesh_logic_data = self.mesh_logic_data.copy()
                    mesh_analog_data = self.mesh_analog_data.copy()
                    
                    data = self.process_logic_data(self.pckNum, self.pckNum + 1)
                    
                    self._mesh_width = ( (self.pckNum * (self._pckLen * self._bitWidth)) * self._scale ) / 2
                    for i, nm in enumerate(mesh_logic_data):
                        self._ranges[i] += int(len(data[nm]) / 3)
                        mesh_logic_data[nm]['data'] = list(data[nm])
                        mesh_logic_data[nm]['range'][1] = self._ranges[i]
                        mesh_logic_data[nm]['pos'] = self._positions[i]
                        self._positions[i] += len(data[nm])
                    
                    for i, nm in enumerate(mesh_analog_data):
                        pass
                        
                    
                    await self.ws_client.send_json({ 'type':'data', 'logic':mesh_logic_data, 'analog':mesh_analog_data })
                    self.pckNum += 1
                    self._has_data -= 1
                    
                
            #STOP SAMPLING indication
            if self.ss_flag.value == 3:
                await self.stop_session()

            await asyncio.sleep(0.01)
#----------------------------------------------
    def process_logic_data(self, start, end):
        packet = {}
        for item in self.channels['logic']:
            packet.update({item['name']:deque()})
        data_slice = np.unpackbits(self.logic_data[start], axis=1)
        data_slice = np.rot90(data_slice)
        for chNum, (ch, pckEntry) in enumerate( zip(data_slice, packet) ):
            pointIndex = 0
            prevVal = -1
            for bitNum, bitVal in enumerate(ch):
                if bitNum <= (self._pckLen) and bitVal != prevVal:
                    pointIndex += 6
                    x1 = (start * self._pckLen * self._bitWidth) + bitNum * self._bitWidth
                    packet[pckEntry].extend([
                        x1,
                        bool(bitVal) * self._bitHeight,
                        0,
                        x1 + self._bitWidth,
                        bool(bitVal) * self._bitHeight,
                        0 ])
                elif bitNum <= (self._pckLen) and bitVal == prevVal:
                    packet[pckEntry][pointIndex-3] += self._bitWidth
                prevVal = bitVal
        return packet
        
    def __del__(self):
            self.client_pipe_A.close()
            self.l_data_task.cancel()
            self.a_data_task.cancel()
            self.sigrok.join()
            self.sigrok.close()

    #async def create_sr_file(self, name):
        #z = zipfile.ZipFile(name, 'w', zipfile.ZIP_DEFLATED)
            
    async def open_sr_file(self, zf):
        z = None
        data_file = None
        config = configparser.ConfigParser()
        try:
            z = zipfile.ZipFile(zf)
            config.read_string(z.read('metadata').decode('ascii'))
            version = config.get('global', 'sigrok version').split('-')[0]
            if version < '0.2.0':
                raise
        except:
            return {'error':'Invalid file'}
        
        capturefile = config.get('device 1', 'capturefile')
        for item in z.namelist():
            if item.startswith(capturefile):
                data_file = z.open(item)
                
        #self.data.clear()
        step = 0
        while step <= data_file.tell():
            data_file.seek(step)
            ar = np.fromstring(data_file.read(512), dtype='uint8')
            ar = np.expand_dims(ar, axis=1)
            self.data.append(ar)
            step += 512
        z.close()
        return {'error':''}
#_____________________________________

class SrProcessManager:
    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self._procs = {}
        self.ses_num = 0
        #self.data_task = self.loop.create_task(self.data_task_coro())

    def get_drivers(self):
        id = next(iter(self._procs))
        proc = self._procs[id]
        drv_list = proc.runcmd('get_drivers')
        return drv_list
        
    def get_sessions(self):
        return [ { 'id':item, 'name':self._procs[item].name } for item in self._procs ]
        
    def create_session(self):
        logger.info(f"{bcolors.WARNING}Create SR session{bcolors.ENDC}")
        name = 'session' + str(self.ses_num)
        id = str(uuid4())
        proc = SrProcessConnection(id, name)
        proc.ws_task = self.loop.create_task(proc.ws_task_coro())
        self._procs[id] = proc
        self.ses_num += 1
        return { 'id':id, 'name': proc.name }
    
    def get_by_id(self, id):
        if id in self._procs:
            proc = self._procs[id]
            return proc
        else:
            return None
    
    def delete_session(self, id):
        logger.info(f"{bcolors.WARNING}Delete SR session{bcolors.ENDC}")
        del self._procs[id]
