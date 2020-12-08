from multiprocessing import Process, Pipe, Queue
from multiprocessing.sharedctypes import Value
from sigrok.core.classes import *
import numpy as np
import asyncio

import os, signal, time, sys, io, itertools, zipfile, configparser
import traceback
from collections import deque, defaultdict

from fastapi.logger import logger

from uuid import uuid4

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class SrProcess(Process):
    """Sigrok process class"""
    def __init__(self, client_pipe, queue, ss_flag, **kwargs):
        super(Process, self).__init__(**kwargs)
        self.ss_flag = ss_flag
        self._context = None
        self._session = None
        self.data_queue = queue
        self.client_pipe = client_pipe
        
        self.response = None
        self.request = None
        
        self._driver = None
        self._devices = None
        self._device = None
        self._pck_num = 0
        
        self._session_param = {
                'sourcename':None,
                'samplerate':'',
                'samplerates':[],
                'sample':None,
                'samples':None,
                'logic':[],
                'analog':[],
            }
        
    def run(self):
        self._context = Context.create()
        self._session = self._context.create_session()
        self._session.add_datafeed_callback(self._datafeed_in_callback)
        while True:
            try:
                self._cmd = self.client_pipe.recv()
                self._cmd.run(self)
            except:
                break
            #if not self._cmd:
                #break
            
    def _datafeed_in_callback(self, device, packet):
        if str(packet.type) == 'LOGIC':
            self._pck_num += 1
            self.data_queue.put(packet.payload.data)
            #print(packet.payload.data.dtype)
            #print(f"{bcolors.WARNING}LOGIC: %s{bcolors.ENDC}" %packet.payload.data)
            
        if str(packet.type) == 'ANALOG':
            #print(f"{bcolors.WARNING}ANALOG: %s{bcolors.ENDC}" %packet.payload.data)
            pass
            
        if str(packet.type) == 'END':
            print(f"{bcolors.WARNING}END sampling{bcolors.ENDC}")
            self._pck_num = 0
            self.ss_flag.value = 3
            
        if self.ss_flag.value == 0 and self._session.is_running():
            print(f"{bcolors.WARNING}STOP sampling{bcolors.ENDC}")
            self._pck_num = 0
            self._session.stop()
            self.ss_flag.value = 3
            
    #NOTE: Sigrok API
    #GET:
    def get_samplerate(self):
        print(f"{bcolors.WARNING}CLI get: samplerate{bcolors.ENDC}")
        response = {'samplerates': self._session_param['samplerates'], 'samplerate': self._session_param['samplerate'] }
        self.client_pipe.send(response)
    
    def get_drivers(self):
        print(f"{bcolors.WARNING}CLI get: drivers_list{bcolors.ENDC}")
        self._driver = None
        response = list(self._context.drivers.keys())
        self.client_pipe.send(response)
        
    def get_scan(self, drv):
        #NOTE: scanning driver
        print(f"{bcolors.WARNING}CLI get: scan %s{bcolors.ENDC}" %drv)
        self._driver = None
        self._driver = self._context.drivers[drv]
        response = []
        if self._driver is not None:
            self._devices = self._driver.scan()
            for device in self._devices:
                response.append({ 'vendor': device.vendor, 'model': device.model, 'driverName': str(device.driver.name), 'connectionId': str(device.connection_id()) })
        self.client_pipe.send(response)
        
    def get_params(self):
        if self._device:
            #try:
                #rates = self._device.config_list(ConfigKey.SAMPLERATE)
                #print('rates_list:', rates)
                #self._session_param['samplerates'] = rates_list
                #analog = []
                #logic = []
                #self._device.config_set(ConfigKey.LIMIT_SAMPLES, 1000000)
                #self._session_param['sample'] = int(1000000)
                #self._session_param['samples'] = [100, 1000, 100000, 1000000]
                #self._session_param['sourcename'] = str(self._driver.name)
                
                #for item in self._device.channels:
                    #if item.type.name == 'ANALOG':
                        #analog.append({'name': item.name })
                    #elif item.type.name == 'LOGIC':
                        #logic.append({'name': item.name })
                #self._session_param['logic'] = logic
                #self._session_param['analog'] = analog
                #rates_list = self._device.config_list(ConfigKey.SAMPLERATE)
                #self._session_param['samplerates'] = rates_list['samplerates']
                #self._session_param['samplerate'] = self._device.config_get(ConfigKey.SAMPLERATE)
            self.client_pipe.send(self._session_param)
            #except AttributeError:
                #print("ERRROOOOOR", AttributeError)
        else:
            self.reset_params()
            self.client_pipe.send(self._session_param)

    #SET:
    def reset_params(self):
        self._session_param = {
            'sourcename':None,
            'samplerate':None,
            'samplerates':None,
            'sample':None,
            'samples':None,
            'logic':[],
            'analog':[],
        }
        
    def gen_list(self, start, ln):
        divs = [2, 5, 10]
        values = []
        mult = 1
        for i in range(1, ln, 1):
            for j in range(2,-1,-1):
                values.append(int(start * 10 / divs[j] * mult))
            mult *= 10
        return values
    
    def set_device_num(self, devNum):
        self.reset_params()
        if self._device is not None:
            self._device.close()
            self._device = None
        self._device = self._devices[devNum]
        analog=[]
        logic=[]
        try:
            self._session.remove_devices()
            self._device.open()
            self._device.config_set(ConfigKey.LIMIT_SAMPLES, 500000)
            self._session.add_device(self._device)
            self._session_param['sourcename'] = self._driver.name
            for item in self._device.channels:
                if item.type.name == 'ANALOG':
                    analog.append({'name': item.name })
                elif item.type.name == 'LOGIC':
                    logic.append({'name': item.name })
            self._session_param['logic'] = logic
            self._session_param['analog'] = analog
            
            self._session_param['sample'] = self._device.config_get(ConfigKey.LIMIT_SAMPLES)
            self._session_param['samples'] = self.gen_list(100, 10)
            
            rates_list = self._device.config_list(ConfigKey.SAMPLERATE)
            if 'samplerates' in rates_list.keys():
                self._session_param['samplerates'] = rates_list['samplerates']
            elif 'samplerate-steps' in rates_list:
                values = self.gen_list(1, 8)
                self._session_param['samplerates'] = values
            self._session_param['samplerate'] = self._device.config_get(ConfigKey.SAMPLERATE)
            
            print(f"{bcolors.OKBLUE}Device open{bcolors.ENDC}")
            self.client_pipe.send('ok')
        except:
            print(f"{bcolors.FAIL}Device NOT open{bcolors.ENDC}")
            self.client_pipe.send('err')
        
    
    def session_run(self, run):
        try:
            print(f"{bcolors.WARNING}START sampling{bcolors.ENDC}")
            self._session.start()
            self._session.run()
        except:
            print(f"{bcolors.WARNING}FAILED Sampling{bcolors.ENDC}")
            self.ss_flag.value = 3
            self.client_pipe.send(False)
        
    def set_samplerate(self, rate):
        print(f"{bcolors.WARNING}CLI set: samplerate %s{bcolors.ENDC}" %rate)
        self._device.config_set(ConfigKey.SAMPLERATE, int(rate))
        self._session_param['samplerate'] = rate
        self.client_pipe.send('ok')
        
    def set_sample(self, num):
        print(f"{bcolors.WARNING}CLI set: samples %s{bcolors.ENDC}" %num)
        self._device.config_set(ConfigKey.LIMIT_SAMPLES, int(num))
        self._session_param['sample'] = int(num)
        self.client_pipe.send('ok')
    #----------------
    
    def __del__(self):
        self.client_pipe.close()
        self.data_queue.close()
            
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
        self.name = name
        self.data_queue = Queue()
        
        self.client_pipe_A, self.client_pipe_B = Pipe()
        self.ss_flag = Value('h', 0)
        
        self.sigrok = SrProcess(self.client_pipe_B, self.data_queue, self.ss_flag)
        self.sigrok.start()
        self.ws_client = None
        self.ws_task = None
        self.data_task = None
        
        self.data = deque()

        self._displayWidth = 1680
        self._has_data = 0
        self._x = None
        self._scale = 1
        self._mesh_width = 1
        #self._camera_pos = 0
        #self._C = None
        self._pckLen = 512
        self._bitWidth = 50 #50 или 1
        self._bitHeight = 50 #50 или 1
        self._positions = list( [0] * 8)
        self._ranges = list( [0] * 8)
        logger.info(f"{bcolors.WARNING}SR pid: %s{bcolors.ENDC}", self.sigrok.pid)
        
    def get_samplerate(self):
        data = self.runcmd('get_samplerate')
        return data
        
    def select_samplerate(self, smp):
        res = self.runcmd('set_samplerate', smp)
    
    def select_sample(self, smpl):
        res = self.runcmd('set_sample', smpl)
    
    def get_params(self):
        data = self.runcmd('get_params')
        #data = {'id':None, 'name':None}
        data['id'] = self.id
        data['name'] = self.name
        return data
        
    def scan_devices(self, drv):
        data = self.runcmd('get_scan', drv)
        return data
    
    def select_device(self, devNum):
        res = self.runcmd('set_device_num', devNum)
        if res == 'ok':
            data = self.get_params()
            return data
        else:
            print('select_device error')
        
    async def start_session(self, run):
        self.data.clear()
        
        #NOTE:START SESSION
        if (run):
            self.ss_flag.value = 1
            request = SrApi('session_run', run)
            self.client_pipe_A.send(request)
            if self.client_pipe_A.poll(0.1):
                resp = self.client_pipe_A.recv()
                await self.ws_client.send_json({ 'type':'config', 'sessionRun':False })
            else: await self.ws_client.send_json({ 'type':'config', 'sessionRun':True })
        
        #NOTE:STOP SESSION
        else:
            self.ss_flag.value = 0
            await self.ws_client.send_json({ 'type':'config', 'sessionRun':False })
            
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
        
    async def update_control_data(self, data):
        for key in data.keys():
            if key == 'scale':
                self._scale = data.get('scale')
                self._mesh_width *= self._scale
                #self._C = (10 / self._scale / 1000) / 2
                
            elif key == 'x':
                self._x = data.get('x')
                self._mesh_width -= self._x
                #self._camera_pos += self._x
                #print(self._camera_pos)
                
            elif key == 'session_run':
                run = data.get('session_run')
                await self.start_session(run)
        
    def runcmd(self, cmd, param = None):
        request = SrApi(cmd, param)
        self.client_pipe_A.send(request)
        try:
            data = self.client_pipe_A.recv()
        except:
            print('error reading data')
        return data
    
    def __del__(self):
            self.data_queue.close()
            self.client_pipe_A.close()
            #os.kill(self.sigrok.pid, signal.SIGINT)
            self.sigrok.join()
            self.sigrok.close()
        
    async def data_task_coro(self):
        #logger.info(f"{bcolors.WARNING}Start data_task{bcolors.ENDC}")
        print(f"{bcolors.OKBLUE}Start data_task{bcolors.ENDC}")
        while True:
            while not self.data_queue.empty():
                data = self.data_queue.get()
                self.data.append(data)
                self._has_data += 1
            else:
                await asyncio.sleep(0.1)
        
    async def ws_task_coro(self):
        #logger.info(f"{bcolors.WARNING}Start ws_task{bcolors.ENDC}")
        print(f"{bcolors.OKBLUE}Start ws_task{bcolors.ENDC}")
        pckNum = 0
        while True:
            if self.ws_client:
                if self._mesh_width < self._displayWidth and self._has_data:
                    mesh_data = {
                        'D0':{'data':[], 'range':[0, 0], 'pos':0},
                        'D1':{'data':[], 'range':[0, 0], 'pos':0},
                        'D2':{'data':[], 'range':[0, 0], 'pos':0},
                        'D3':{'data':[], 'range':[0, 0], 'pos':0},
                        'D4':{'data':[], 'range':[0, 0], 'pos':0},
                        'D5':{'data':[], 'range':[0, 0], 'pos':0},
                        'D6':{'data':[], 'range':[0, 0], 'pos':0},
                        'D7':{'data':[], 'range':[0, 0], 'pos':0}
                    }
                    
                    data = self.process_data(pckNum, pckNum + 1)
                    
                    self._mesh_width = ( (pckNum * (self._pckLen * self._bitWidth)) * self._scale ) / 2
                    for i, nm in enumerate(mesh_data):
                        self._ranges[i] += int(len(data[nm]) / 3)
                        mesh_data[nm]['data'] = list(data[nm])
                        mesh_data[nm]['range'][1] = self._ranges[i]
                        mesh_data[nm]['pos'] = self._positions[i]
                        self._positions[i] += len(data[nm])
                    await self.ws_client.send_json({ 'type':'data', 'data':mesh_data })
                    pckNum += 1
                    self._has_data -= 1
                
            #END PACKET/ERROR SESSION
                if self.ss_flag.value == 3:
                    self.ss_flag.value = 0
                    await self.ws_client.send_json({ 'type':'config', 'sessionRun':False })
            await asyncio.sleep(0.01)

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

class SrProcessManager:
    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self._procs = {}
        self.ses_num = 0
        
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
        #proc.data_task = self.loop.create_task(proc.data_task_coro())
        #proc.ws_task = self.loop.create_task(proc.ws_task_coro())
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
        #proc.data_task.cancel()
        #proc.ws_task.cancel()
        logger.info(f"{bcolors.WARNING}Delete SR session{bcolors.ENDC}")
        del self._procs[id]
