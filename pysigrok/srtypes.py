from dataclasses import dataclass, asdict, field, make_dataclass
from typing import List, Union, Any, Dict
from enum import Enum
from sigrok.core.classes import ConfigKey

__all__ = [
    "SrBlankState",
    "SrDeviceState",
    #"SrFileState",
    #"AnalogChannel",
    #"LogicChannel",
]

colorsArray = [
    '#fce94f', '#fcaf3e', '#e9b96e', '#8ae234', '#729fcf', '#ad7fa8', '#cf72c3', '#ef2929',
    '#edd400', '#f57900', '#c17d11', '#73d216', '#3465a4', '#75507b', '#a33496', '#cc0000',
    '#c4a000', '#ce5c00', '#8f5902', '#4e9a06', '#204a87', '#5c3566', '#87207a', '#a40000',
    '#16191a', '#2e3436', '#555753', '#888a8f', '#babdb6', '#d3d7cf', '#eeeeec', '#ffffff'
]

def factory(data):
    return dict(x for x in data if x[1] is not None)

def build_opts(opts: list):
    #NOTE: key, id, name, desc, keyName, caps
    data = []
    for opt in opts:
        bases = []
        opt_fields = []
        if 'caps' in opt:
            if 'LIST' in opt['caps']:
                bases.append(ConfList)
            elif 'GET' in opt['caps']:
                bases.append(ConfValue)
                
        for k, v in opt.items():
            opt_fields.append((k, type(v)))
    
        opt_fields.append( ('keyName', str))
        
        keyName=ConfigKey.get(opt['key']).name
        
        SrOpt = make_dataclass(cls_name='SrOpt', fields=opt_fields, bases=tuple(bases))
        srOpt = SrOpt(**opt, keyName = keyName)
        
        
        data.append( (keyName, srOpt) )
    
    return data

@dataclass
class ConfValue:
    value: Any

@dataclass
class ConfList:
    values: List[Any] = field(default_factory=list)

@dataclass
class Channel:
    name: str
    text: str
    color: str
    enabled: bool
    index: int
    type: str
    
    def update(self, opts: Dict):
        for key, value in opts.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
@dataclass
class LogicChannel(Channel):
    traceHeight: int = 34
    
@dataclass
class AnalogChannel(Channel):
    pVertDivs: int = 1
    nVertDivs: int = 1
    divHeight: int = 51
    vRes: float = 20.0
    autoranging: bool = True
    conversion: str = ''
    convThres: str = ''
    showTraces: str = ''
    

class ChTypesEnum(Enum):
    analog = AnalogChannel
    logic = LogicChannel
    

@dataclass
class ChnlsContBase:
    def set(self, chOpts: List[Dict] ):
        result = []
        for opts in chOpts:
            chName = opts.pop('chName', None)
            if hasattr(self, chName):
                attr = getattr(self, chName)
                attr.update(opts)
                result.append(chName)
        return result
    
    def get(self):
        data = asdict(self, dict_factory=factory)
        return data.values()
    
    def get_list(self):
        data = asdict(self, dict_factory=factory)
        return list( { item['type'] for item in data.values() })
    
@dataclass
class OptsContBase:
    def set(self, opts: List[Dict] ):
        result = []
        for item in opts:
            optName = item['keyName']
            if hasattr(self, optName):
                attr = getattr(self, optName)
                attr.value = item['value']
                result.append(optName)
        return result
    
    def get(self):
        return asdict(self, dict_factory=factory)
    
    def get_list(self):
        data = [ item['key'] for item in asdict(self).values() ] #list(asdict(self).values()
        return  data

def make_ch_container(channels: List[Dict]):
    fields = []
    for i, item in enumerate(channels):
        chInst = ChTypesEnum[item['type']].value(**item, color= colorsArray[i], text=item['name'])
        fields.append( ( item['name'], chInst) )
        
    ChnlsContainer = make_dataclass('ChnlsContainer', [ item[0] for item in fields], bases=tuple([ChnlsContBase]) )
    data = ChnlsContainer(**{ item[0]: item[1] for item in fields})
    return data

def make_opts_container(opts: List[Dict]):
    fields = build_opts(opts)
    OptsContainer = make_dataclass('OptsContainer', [ item[0] for item in fields], bases=tuple([OptsContBase]))
    data = OptsContainer(**{ item[0]: item[1] for item in fields})
    return data

#-----------------  STATE TYPES   -----------------#
@dataclass
class SrBlankState:
    id: str
    name: str
    sourcename: str
    type: str = field(init=False)
    
    def __post_init__(self):
        self.type = "BLANK"
    
    def get(self):
        data = asdict(self, dict_factory=factory)
        return data
    
@dataclass
class SrDeviceState(SrBlankState):
    drvopts: Dict[ str, Any ]
    devopts: Dict[ str, Any ]
    channels: Dict[ str, Union[ AnalogChannel, LogicChannel ] ]#Any
    
    def __init__(self, id, name, sourcename, drvopts: List, devopts: List, channels: List[ChTypesEnum]):
        SrBlankState.__init__(self, id, name, sourcename)
        self.type = 'DEVICE'
        self.drvopts = make_opts_container(drvopts)
        self.devopts = make_opts_container(devopts)
        
        self.channels = make_ch_container(channels)
    
    def get(self):
        data = super().get()
        
        data['drvopts'] = self.drvopts.get_list()
        data['devopts'] = self.devopts.get_list()
        data['channels'] = self.channels.get_list()
        
        return data
