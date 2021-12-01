from ariadne import  make_executable_schema, QueryType, ObjectType, InterfaceType, MutationType, EnumType, load_schema_from_path
from sigrok.core.classes import ConfigKey
from .srtypes import SrDeviceState, SrBlankState
from .srresolver import srResolver
from sigrok.core.classes import get_drivers
from .srprocmng import srMng

driversList = get_drivers()

type_defs = load_schema_from_path("./")
enum_defs = "enum ConfKey {" + " ".join(str(e) for e in ConfigKey.values()) + "}"

query = QueryType()
mutation = MutationType()
sessionType = InterfaceType('Session')
channelType = InterfaceType('Channel')
optionType = InterfaceType('Option')

confDict = { item.name: item.id for item in ConfigKey.values() }
confEnumType = EnumType('ConfKey', confDict)

#---------QUERIES----------
@query.field("chanList")
async def resolve_channel(proc, info):
    data = proc._state.channels.get()
    return data

@channelType.type_resolver
async def resolve_channel_type(obj, *_):
    if obj['type'] == 'analog':
        return 'AnalogChannel'
    if obj['type'] == 'logic':
        return 'LogicChannel'
    return None

@query.field("options")
def resolve_options(proc, info, opts):
    data = proc.get_options(opts)
    return data

@optionType.type_resolver
def resolve_option_type(obj, *_):
    if 'caps' not in obj:
        return 'EmptyOpt'
    elif 'GET' in obj['caps'] and not 'LIST' in obj['caps']:
        return 'ValueOpt'
    elif 'LIST' in obj['caps'] and not 'GET' in obj['caps']:
        return 'ListOpt'
    else:
        return 'VlOpt'

@sessionType.type_resolver
def resolve_session_type(obj, info, *_):
    if obj['type'] == 'BLANK':
        return 'BlankSession'
    elif obj['type'] == 'DEVICE':
        return 'DeviceSession'
    return None

@query.field("session")
async def resolve_session(proc, info):
    return proc.session_state

#RESOLVE SESSIONS LIST
@query.field("sessions")
async def resolve_sessions(srmng, info):
    data = srmng.get_sessions()
    return { 'sesList': data, 'session': data[0]}

@query.field("drivers")
async def resolve_drivers(_, info):
    return driversList

@query.field("decodersList")   
async def resolve_decoders(proc, info):
    return []

@query.field("scanDevices")
async def resolve_scanDevices(proc, info, drv):
    data = await proc.scan_devices(drv)
    return data

#-------MUTATIONS-------
#ATTENTION
@mutation.field("setChannelOptions")
async def resolve_setChannelOpts(proc, info, input: list):
    data = await proc.set_channels_options(input)
    return data

#ATTENTION
@mutation.field("setOptions")
async def resolve_setOptions(proc, info, opts: list):
    data = await proc.set_options(opt, opts)
    return data


@mutation.field("selectDevice")
async def resolve_selectDevice(proc, info, devNum):
    data = await proc.select_device(devNum)
    return data

@mutation.field("createSession")
async def resolve_createSession(srmng, info):
    data = await srmng.create_session()
    return data

@mutation.field("deleteSession")
async def resolve_deleteSession(srmng, info, id):
    rid = srmng.end_proc(id)
    return { 'id': rid, 'success':True}

srSchema = make_executable_schema([type_defs, enum_defs], [query, mutation, sessionType, channelType, confEnumType, optionType, srResolver ])
