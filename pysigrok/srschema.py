from ariadne import  make_executable_schema, QueryType, ObjectType, InterfaceType, MutationType, EnumType, load_schema_from_path
from sigrok.core.classes import ConfigKey
from .srtypes import SrDeviceState, SrBlankState
from .srresolver import srResolver
from sigrok.core.classes import get_drivers

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
@query.field("channelsList")
async def resolve_channel(mng, info, id):
    proc = mng.get_by_id(id)
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
def resolve_options(mng, info, id, opts):
    proc = mng.get_by_id(id)
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
def resolve_session(srmng, info, id):
    proc = srmng.get_by_id(id)
    return proc.session_state

#RESOLVE SESSIONS LIST
@query.field("sessions")
async def resolve_sessions(srmng, info):
    data = srmng.get_sessions()
    return data

@query.field("drivers")
async def resolve_drivers(srmng, info):
    #id = next(iter(srmng._procs))
    #proc = srmng.get_by_id(id)
    #data = await proc.get_drivers()
    return get_drivers()

@query.field("decodersList")   
async def resolve_decoders(_, info, id):
    #proc = info.context['srmng'].get_by_id(id)
    #data = await proc.get_decoders_list()
    return []

@query.field("scanDevices")
async def resolve_scanDevices(mng, info, id, drv):
    proc = mng.get_by_id(id)
    data = await proc.scan_devices(drv)
    
    return data

#-------MUTATIONS-------
#ATTENTION
@mutation.field("setChannelOptions")
async def resolve_setChannelOpts(mng, info, id, input: list):
    proc = mng.get_by_id(id)
    data = await proc.set_channels_options(input)#TODO
    return data

#ATTENTION
@mutation.field("setOptions")
async def resolve_setOptions(mng, info, id, opts: list):
    proc = mng.get_by_id(id)
    data = await proc.set_options(opt, opts)#TODO
    return data

#@mutation.field("setOption")
#async def resolve_setOption(_, info, id, opt, value):
    #proc = info.context['srmng'].get_by_id(id)
    #data = await proc.set_option(opt, value)
    #return data

@mutation.field("selectDevice")
async def resolve_selectDevice(mng, info, id, devNum):
    proc = mng.get_by_id(id)
    data = await proc.select_device(devNum)
    return data

@mutation.field("createSession")
async def resolve_createSession(mng, info):
    data = await mng.create_session()
    return data

@mutation.field("deleteSession")
async def resolve_deleteSession(_, info, id):
    rid = mng.delete_session(id)
    return rid

srSchema = make_executable_schema([type_defs, enum_defs], [query, mutation, sessionType, channelType, confEnumType, optionType, srResolver])
