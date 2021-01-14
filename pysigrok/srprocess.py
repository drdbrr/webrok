from multiprocessing import Process
from sigrok.core.classes import *
import socket
import numpy as np

tmp_dir = '/tmp/webrok/'

colorsArray = [
    '#fce94f', '#fcaf3e', '#e9b96e', '#8ae234', '#729fcf', '#ad7fa8', '#cf72c3', '#ef2929',
    '#edd400', '#f57900', '#c17d11', '#73d216', '#3465a4', '#75507b', '#a33496', '#cc0000',
    '#c4a000', '#ce5c00', '#8f5902', '#4e9a06', '#204a87', '#5c3566', '#87207a', '#a40000',
    '#16191a', '#2e3436', '#555753', '#888a8f', '#babdb6', '#d3d7cf', '#eeeeec', '#ffffff'
]

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
    def __init__(self, client_pipe, ss_flag, **kwargs):
        super(Process, self).__init__(**kwargs)
        self.ss_flag = ss_flag
        self._context = None
        self._session = None
        self.client_pipe = client_pipe
        
        self.response = None
        self.request = None
        
        self._driver = None
        self._devices = None
        self._device = None
        self._logic_pck_num = 0
        self._analog_pck_num = 0
        
        self._session_param = {
            'id':'',
            'name':'',
            'type':'',
            'sourcename':'',
            'samplerate':'',
            'samplerates':[],
            'sample':'',
            'samples':[],
            'config':[],
            'channels':[]
        }
        
        self._logic_channels = []
        self._analog_channels = []
        
        self.lsock = None
        self.asock = None
        
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
            
    def _datafeed_in_callback(self, device, packet):
        if str(packet.type) == 'LOGIC':
            self._logic_pck_num += 1
            self.lconn.sendall(packet.payload.data.tobytes())
            
        if str(packet.type) == 'ANALOG':
            self._analog_pck_num += 1
            self.aconn.sendall(packet.payload.data[0].tobytes())

        if str(packet.type) == 'END':
            print(f"{bcolors.WARNING}END sampling{bcolors.ENDC}")
            self.ss_flag.value = 3
            print('TX analog packets:', self._analog_pck_num)
            print('TX  logic packets:', self._logic_pck_num)
            
            self._analog_pck_num = 0
            self._logic_pck_num = 0
            
        if self.ss_flag.value == 0 and self._session.is_running():
            print(f"{bcolors.WARNING}STOP sampling{bcolors.ENDC}")
            self._session.stop()
            self.ss_flag.value = 3
            
            print('TX analog packets:', self._analog_pck_num)
            print('TX  logic packets:', self._logic_pck_num)
            self._analog_pck_num = 0
            self._logic_pck_num = 0

    #NOTE: Sigrok API
    #GET:
    def get_channels(self):
        print(f"{bcolors.WARNING}CLI get: channels list{bcolors.ENDC}")
        self.client_pipe.send({'logic':self._logic_channels, 'analog':self._analog_channels})

    def get_sample(self):
        print(f"{bcolors.WARNING}CLI get: sample number{bcolors.ENDC}")
        response = {'samples': self._session_param['samples'], 'sample': self._session_param['sample'] }
        self.client_pipe.send(response)

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

    def get_session(self):
        if self._device:
            self.client_pipe.send({'id':'', 'name':'', 'type':'device', 'sourcename':self._session_param['sourcename'],'config':self._session_param['config'], 'channels':self._session_param['channels']})
        else:
            self.reset_params()
            self.client_pipe.send({'id':'', 'name':'', 'type':'', 'sourcename':'', 'config':[], 'channels':[]})

    #SET:
    def reset_params(self):
        self._session_param = {
            'id':'',
            'name':'',
            'type':'',
            'sourcename':'',
            'samplerate':'',
            'samplerates':[],
            'sample':'',
            'samples':[],
            'config':[],
            'channels':[]
        }
        self._analog_channels = []
        self._logic_channels = []
        
        
        if self._device is not None:
            self._device.close()
            self._device = None
            self._session.remove_devices()
        
        if self.asock is not None:
            self.asock.close()
            self.asock = None
            
        if self.lsock is not None:
            self.lsock.close()
            self.lsock = None

    def gen_list(self, start, ln):
        divs = [2, 5, 10]
        values = []
        mult = 1
        for i in range(1, ln, 1):
            for j in range(2,-1,-1):
                values.append(int(start * 10 / divs[j] * mult))
            mult *= 10
        return values
    
    def create_sock(self, path):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(path)
        sock.listen(1)
        return sock

    def set_device_num(self, devNum):
        self.reset_params()
        self._device = self._devices[devNum]
        
        lswa = False #logic socket wait accepting
        aswa = False #analog socket wait accepting
        
        try:
            #self._session.remove_devices()
            self._device.open()
            print(f"{bcolors.OKBLUE}Device open{bcolors.ENDC}")
            self._device.config_set(ConfigKey.LIMIT_SAMPLES, 500000)
            self._session.add_device(self._device)
            self._session_param['sourcename'] = self._driver.name
            self._session_param['sample'] = self._device.config_get(ConfigKey.LIMIT_SAMPLES)
            self._session_param['samples'] = self.gen_list(100, 10)

            rates_list = self._device.config_list(ConfigKey.SAMPLERATE)
            if 'samplerates' in rates_list.keys():
                self._session_param['samplerates'] = rates_list['samplerates']
            elif 'samplerate-steps' in rates_list:
                values = self.gen_list(1, 8)
                self._session_param['samplerates'] = values
            self._session_param['samplerate'] = self._device.config_get(ConfigKey.SAMPLERATE)
            
            for i, item in enumerate(self._device.channels):
                if item.type.name == 'LOGIC':
                    self._logic_channels.append({'name': item.name, 'text':item.name, 'color':colorsArray[i], 'visible':True, 'traceHeight':34 })
                    
                elif item.type.name == 'ANALOG':
                    self._analog_channels.append({'name': item.name, 'text':item.name, 'color':colorsArray[i], 'visible':True, 'pVertDivs':1, 'nVertDivs':1, 'divHeight':34, 'vRes':20.0, 'autoranging':True, 'conversion':'', 'convThres':'', 'showTraces':'' })

            resonse = {}
            if 'Logic' in self._device.channel_groups:
                self.lsock = self.create_sock(tmp_dir + self.name + 'lsock')
                self._session_param['channels'].append('LOGIC')
                lswa = True
                resonse.update({'logic':self._logic_channels})
                
            if 'Analog' in self._device.channel_groups:
                self.asock = self.create_sock(tmp_dir + self.name + 'asock')
                self._session_param['channels'].append('ANALOG')
                aswa = True
                resonse.update({'analog':self._analog_channels})

            for item in self._device.config_keys():
                    self._session_param['config'].append(str(item))
            
            self.client_pipe.send(resonse)
            #self.client_pipe.send(self._session_param['channels'])
            
            if lswa:
                self.lconn, addr = self.lsock.accept()
                print('lsoc accepted')
                
            if aswa:
                self.aconn, addr = self.asock.accept()
                print('asoc accepted')
            
        except:
            print(f"{bcolors.FAIL}Can NOT open device{bcolors.ENDC}")
            self.client_pipe.send(False)
        
    
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
        self.asock.close()
        self.lsock.close()
