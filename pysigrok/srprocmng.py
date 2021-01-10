from multiprocessing import Process, Pipe, Queue, Event, Value
import numpy as np
import asyncio

import os, signal, time, sys, io, itertools, zipfile, configparser, time, array
import traceback
from collections import deque, defaultdict

from fastapi.logger import logger

from uuid import uuid4

from .srprocess import SrProcess

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
        
        self.data = {'logic':deque(), 'analog':deque()}

        self._displayWidth = 1680
        self._has_data = 0
        self._x = 0
        self._scale = 1
        self._mesh_width = 1
        #self._camera_pos = 0
        #self._C = None
        self._pckLen = 512
        self._bitWidth = 50 #50 или 1
        self._bitHeight = 50 #50 или 1
        self._positions = list( [0] * 8)
        self._ranges = list( [0] * 8)
        
        self.bt = 0
        
        self._logic_pck_num = 0
        self._analog_pck_num = 0
        
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
        res = self.runcmd('set_device_num', devNum)
        
        loop = asyncio.get_event_loop()
        
        if res:
            if 'LOGIC' in res:
                print('Open lsock')
                self.lreader, wr = await asyncio.open_unix_connection(tmp_dir + self.id + 'lsock')
                
                self.l_data_task = loop.create_task(self.ldata_handler_task())
                
            if 'ANALOG' in res:
                print('Open asock')
                self.areader, wr = await asyncio.open_unix_connection(tmp_dir + self.id + 'asock')
                
                self.a_data_task = loop.create_task(self.adata_handler_task())
                
            data = self.get_session()    
            return data
        else:
            print('Error selecting device')
            
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
        self.data['analog'].clear()
        self.data['logic'].clear()
        #self._has_data = 0
        
        self._logic_pck_num = 0
        self._analog_pck_num = 0
        
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
        print('Session deltaT:', time.time() - self.bt)
        await self.ws_client.send_json({ 'type':'config', 'sessionRun':False })
        
    def update_scale(self, data):
        self._scale = data
        print('scale:', self._scale)
        #self._mesh_width *= self._scale
        
    def update_x(self, x):
        self._x += x
        print('x:', self._x)
        #self._mesh_width -= self._x
        
    async def ldata_handler_task(self):
        print(f"{bcolors.OKBLUE}Start data_task{bcolors.ENDC}")
        while True:
            data = await self.lreader.read(4096)
            if data:
                self.data['logic'].append(np.frombuffer(data, dtype='uint8'))
                self._logic_pck_num += 1
                #await self.ws_client.send_json({ 'type':'cnt', 'pck_cnt': self._has_data})
            else:
                break
        
    async def adata_handler_task(self):
        print(f"{bcolors.OKBLUE}Start data_task{bcolors.ENDC}")
        while True:
            data = await self.areader.read(4096)
            if data:
                self.data['analog'].append(np.frombuffer(data, dtype='float32'))
                self._analog_pck_num += 1
                #await self.ws_client.send_json({ 'type':'cnt', 'pck_cnt': self._has_data})
            else:
                break
        
    async def ws_task_coro(self):
        #logger.info(f"{bcolors.WARNING}Start ws_task{bcolors.ENDC}")
        print(f"{bcolors.OKBLUE}Start ws_task{bcolors.ENDC}")
        pckNum = 0
        while True:
            if self.ws_client:
                #if self._mesh_width < self._displayWidth and self._has_data:
                    #mesh_data = {
                        #'D0':{'data':[], 'range':[0, 0], 'pos':0},
                        #'D1':{'data':[], 'range':[0, 0], 'pos':0},
                        #'D2':{'data':[], 'range':[0, 0], 'pos':0},
                        #'D3':{'data':[], 'range':[0, 0], 'pos':0},
                        #'D4':{'data':[], 'range':[0, 0], 'pos':0},
                        #'D5':{'data':[], 'range':[0, 0], 'pos':0},
                        #'D6':{'data':[], 'range':[0, 0], 'pos':0},
                        #'D7':{'data':[], 'range':[0, 0], 'pos':0}
                    #}
                    
                    #data = self.process_data(pckNum, pckNum + 1)
                    
                    #self._mesh_width = ( (pckNum * (self._pckLen * self._bitWidth)) * self._scale ) / 2
                    #for i, nm in enumerate(mesh_data):
                        #self._ranges[i] += int(len(data[nm]) / 3)
                        #mesh_data[nm]['data'] = list(data[nm])
                        #mesh_data[nm]['range'][1] = self._ranges[i]
                        #mesh_data[nm]['pos'] = self._positions[i]
                        #self._positions[i] += len(data[nm])
                    #await self.ws_client.send_json({ 'type':'data', 'data':mesh_data })
                    #pckNum += 1
                    #self._has_data -= 1
                
            #END PACKET/ERROR SESSION
                if self.ss_flag.value == 3:
                    await self.stop_session()
                    
            await asyncio.sleep(0.1)
#----------------------------------------------


    #NOTE: (start, end) - packet numbers
    def process_data(self, start, end):
        packet = { 'D0':deque(), 'D1':deque(), 'D2':deque(), 'D3':deque(), 'D4':deque(), 'D5':deque(), 'D6':deque(), 'D7':deque() }
        data_slice = np.unpackbits(self.data[start], axis=1)
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
            #os.kill(self.sigrok.pid, signal.SIGINT)
            self.sigrok.join()
            self.sigrok.close()

    async def create_sr_file(self, name):
        z = zipfile.ZipFile(name, 'w', zipfile.ZIP_DEFLATED)
            
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
                
        self.data.clear()
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
