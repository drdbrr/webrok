import graphene
from graphql import GraphQLError
import time

#---------API---------#
# info.context['srmng'] = SrProcessManager: create_session:id, delete_session(id), get_sessions:[id], get_drivers:[drv], get_by_id(id):proc, get_session(id):{params}
# SrProcessConnection: scan_devices(drv):[devices], select_device(num):{params}
#---------API---------#

#---------TYPES---------#


#--------BEGIN PD--------#
class DecoderOptions(graphene.ObjectType):
    id = graphene.String(default_value='')
    desc = graphene.String(default_value='')
    type = graphene.String(default_value='')
    defv = graphene.String(default_value='')
    values = graphene.List(graphene.String)#, default_value = [])
    
class DecoderAnnotationRow(graphene.ObjectType):
    id = graphene.String(default_value='')
    desc = graphene.String(default_value='')
    #ann_classes = graphene.List(graphene.Int)
    
#ATTENTION нужен ли данный тип??????
#class DecoderAnnotations(graphene.ObjectType):
    #key = graphene.String(default_value='')
    #text = graphene.String(default_value='')
    
class SrdChannel(graphene.ObjectType):
    id = graphene.String()
    name = graphene.String()
    desc = graphene.String()

class Decoder(graphene.ObjectType):
    id = graphene.String()
    name = graphene.String()
    longname = graphene.String()
    desc = graphene.String()
    license = graphene.String()
    tags = graphene.List(graphene.String, default_value = [])
    doc = graphene.String()#ATTENTION
    options = graphene.List(DecoderOptions)
    annotationRows = graphene.List(DecoderAnnotationRow)
    channels = graphene.List(SrdChannel)
    optChannels = graphene.List(SrdChannel)
#--------END PD--------#
    

class Sample(graphene.ObjectType):
    samples = graphene.List(graphene.String, default_value = [])
    sample = graphene.String(default_value='')

class Samplerate(graphene.ObjectType):
    samplerates = graphene.List(graphene.String, default_value = [])
    samplerate = graphene.String(default_value='')

class DeviceInfo(graphene.ObjectType):
    vendor = graphene.String(default_value='')
    model = graphene.String(default_value='')
    driverName = graphene.String(default_value='')
    connectionId = graphene.String(default_value='')
    
class Session(graphene.ObjectType):
    id = graphene.ID()
    type = graphene.String(default_value='')
    name = graphene.String(default_value='')
    sourcename = graphene.String(default_value='')
    config = graphene.List(graphene.NonNull(graphene.String))
    channels = graphene.List(graphene.NonNull(graphene.String))

class LogicChannel(graphene.ObjectType):
    name = graphene.String()
    text = graphene.String()
    color = graphene.String()
    visible = graphene.Boolean(default_value=True)
    #index = graphene.Int()
    traceHeight = graphene.Int(default_value=34)
    
class AnalogChannel(graphene.ObjectType):
    name = graphene.String()
    text = graphene.String()
    color = graphene.String()
    visible = graphene.Boolean(default_value=True)
    #index = graphene.Int()
    pVertDivs = graphene.Int(default_value=1)
    nVertDivs = graphene.Int(default_value=1)
    divHeight = graphene.Int(default_value=50)
    vRes = graphene.Float(default_value=20.0)
    autoranging = graphene.Boolean(default_value=True)
    conversion = graphene.String(default_value='')
    convThres = graphene.String(default_value='')
    showTraces = graphene.String(default_value='')
    
class DecoderChannel(graphene.ObjectType):
    name = graphene.String()
    stackName = graphene.String()
    
class Channels(graphene.ObjectType):
    logic = graphene.List(LogicChannel)
    analog = graphene.List(AnalogChannel)
    

class Driver(graphene.ObjectType):
    driverName = graphene.String(default_value='')
    vendor = graphene.String(default_value='')
    model = graphene.String(default_value='')
    connectionId = graphene.String(default_value='')

#---------QUERIES---------#
class SrQuery(graphene.ObjectType):
    sessions = graphene.List(Session)
    session = graphene.Field(Session, id=graphene.ID(required=True))
    drivers = graphene.List(graphene.String, default_value = [])
    scanDevices = graphene.List(DeviceInfo, id=graphene.ID(required=True), drv=graphene.String(required=True))
    samplerate = graphene.Field(Samplerate, id=graphene.ID(required=True))
    sample = graphene.Field(Sample, id=graphene.ID(required=True))
    
    getChannels = graphene.Field(Channels, id=graphene.ID(required=True))
    
    decodersList = graphene.List(Decoder, default_value = [], id=graphene.ID(required=True))
    
    async def resolve_decodersList(self, info:graphene.ResolveInfo, id):
        proc = info.context['srmng'].get_by_id(id)
        data = await proc.get_decoders_list()
        return [ Decoder(**item) for item in data ]
    
    async def resolve_getChannels(self, info:graphene.ResolveInfo, id):
        proc = info.context['srmng'].get_by_id(id)
        data = await proc.get_channels()
        analog = []
        logic=[]
        for item in data['logic']:
            logic.append(LogicChannel(**item))
            
        for item in data['analog']:
            analog.append(AnalogChannel(**item))
        
        return Channels(analog=analog, logic=logic)
    
    async def resolve_sample(self, info:graphene.ResolveInfo, id):
        proc = info.context['srmng'].get_by_id(id)
        data = await proc.get_sample()
        return Sample(**data)
    
    async def resolve_samplerate(self, info:graphene.ResolveInfo, id):
        proc = info.context['srmng'].get_by_id(id)
        data = await proc.get_samplerate()
        return Samplerate(**data)
    
    async def resolve_scanDevices(self, info:graphene.ResolveInfo, id, drv):
        proc = info.context['srmng'].get_by_id(id)
        data = await proc.scan_devices(drv)
        return [ DeviceInfo(**item) for item in data ]
    
    async def resolve_drivers(self, info:graphene.ResolveInfo):
        #srmngg = info.context['request'].scope.get('srmngg')
        #print(srmngg)
        try:
            id = next(iter(info.context['srmng']._procs))
            proc = info.context['srmng'].get_by_id(id)
            data = await proc.get_drivers()
            return data
        except:
            raise GraphQLError('Error getting drivers')
    
    async def resolve_sessions(self, info:graphene.ResolveInfo):
        data = info.context['srmng'].get_sessions()
        return [ Session(**item) for item in data ]
    
    async def resolve_session(self, info:graphene.ResolveInfo, id):
        proc = info.context['srmng'].get_by_id(id)
        data = await proc.get_session()
        return Session(**data)

#---------MUTATIONS---------#
class SelectDecoder(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        pdId = graphene.String(required=True)
        
    Output = Decoder
    
    async def mutate(self, info:graphene.ResolveInfo, id, pdId):
        try:
            proc = info.context['srmng'].get_by_id(id)
            data = await proc.register_pd(pdId)
            return Decoder(**data)
        except:
            raise GraphQLError('Error register PD')


class SelectDevice(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        devNum = graphene.Int(required=True)
        
    Output = Session
        
    async def mutate(self, info:graphene.ResolveInfo, id, devNum):
        try:
            proc = info.context['srmng'].get_by_id(id)
            data = await proc.select_device(devNum)
            return Session(**data)
        except:
            raise GraphQLError('Error selecting device')

class CreateSession(graphene.Mutation):
    Output = Session
    async def mutate(self, info:graphene.ResolveInfo):
        try:
            data = await info.context['srmng'].create_session()
            return Session(**data)
        except:
            raise GraphQLError('Error creating session')

class DeleteSession(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
    id = graphene.ID()
    async def mutate(self, info:graphene.ResolveInfo, id):
        try:
            rid = await info.context['srmng'].delete_session(id)
            return DeleteSession(id=rid)
        except:
            raise GraphQLError("Error deleting session")
        
class SelectSamplerate(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        samplerate = graphene.String(required=True)
        
    id = graphene.ID()
    samplerate = graphene.String()
    
    async def mutate(self, info:graphene.ResolveInfo, id, samplerate):
        proc = info.context['srmng'].get_by_id(id)
        resp = await proc.select_samplerate(samplerate)
        if resp == 'set':
            return SelectSamplerate(id=id, samplerate=samplerate)
        else:
            raise GraphQLError("Error selecting samplerate")

class SelectSample(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        sample = graphene.String(required=True)
        
    id = graphene.ID()
    sample = graphene.String()
    
    async def mutate(self, info:graphene.ResolveInfo, id, sample):
        proc = info.context['srmng'].get_by_id(id)
        resp = await proc.select_sample(sample)
        if resp == 'set':
            return SelectSample(id=id, sample=sample)
        else:
            raise GraphQLError("Error selecting sample numbers")

class SrMutation(graphene.ObjectType):
    createSession = CreateSession.Field()
    deleteSession = DeleteSession.Field()
    selectDevice = SelectDevice.Field()
    selectSamplerate = SelectSamplerate.Field()
    selectSample = SelectSample.Field()
    selectDecoder = SelectDecoder.Field()
