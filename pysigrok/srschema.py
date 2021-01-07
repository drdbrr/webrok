import graphene
from graphql import GraphQLError

#---------API---------#
# info.context['srmng'] = SrProcessManager: create_session:id, delete_session(id), get_sessions:[id], get_drivers:[drv], get_by_id(id):proc, get_session(id):{params}
# SrProcessConnection: scan_devices(drv):[devices], select_device(num):{params}
#---------API---------#

#---------TYPES---------#

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
    
class Channels(graphene.ObjectType):
    logic = graphene.List(LogicChannel)
    analog = graphene.List(AnalogChannel)

#---------QUERIES---------#
class SrQuery(graphene.ObjectType):
    sessions = graphene.List(Session)
    session = graphene.Field(Session, id=graphene.ID(required=True))
    drivers = graphene.List(graphene.String, default_value = [])
    scanDevices = graphene.List(DeviceInfo, id=graphene.ID(required=True), drv=graphene.String(required=True))
    samplerate = graphene.Field(Samplerate, id=graphene.ID(required=True))
    sample = graphene.Field(Sample, id=graphene.ID(required=True))
    
    getChannels = graphene.Field(Channels, id=graphene.ID(required=True))
    
    async def resolve_getChannels(self, info:graphene.ResolveInfo, id):
        proc = info.context['srmng'].get_by_id(id)
        data = proc.get_channels()
        analog = []
        logic=[]
        for item in data['logic']:
            logic.append(LogicChannel(**item))
            
        for item in data['analog']:
            analog.append(AnalogChannel(**item))
        
        return Channels(analog=analog, logic=logic)
    
    async def resolve_sample(self, info:graphene.ResolveInfo, id):
        proc = info.context['srmng'].get_by_id(id)
        data = proc.get_sample()
        return Sample(**data)
    
    async def resolve_samplerate(self, info:graphene.ResolveInfo, id):
        proc = info.context['srmng'].get_by_id(id)
        data = proc.get_samplerate()
        return Samplerate(**data)
    
    async def resolve_scanDevices(self, info:graphene.ResolveInfo, id, drv):
        proc = info.context['srmng'].get_by_id(id)
        data = proc.scan_devices(drv)
        return [ DeviceInfo(**item) for item in data ]
    
    async def resolve_drivers(self, info:graphene.ResolveInfo):
        try:
            data = info.context['srmng'].get_drivers()
            return data
        except:
            raise GraphQLError('Error getting drivers')
    
    async def resolve_sessions(self, info:graphene.ResolveInfo):
        data = info.context['srmng'].get_sessions()
        return [ Session(**item) for item in data ]
    
    async def resolve_session(self, info:graphene.ResolveInfo, id):
        proc = info.context['srmng'].get_by_id(id)
        data = proc.get_session()
        return Session(**data)

#---------MUTATIONS---------#
class SelectDevice(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        devNum = graphene.Int(required=True)
        
    Output = Session
        
    async def mutate(self, info:graphene.ResolveInfo, id, devNum):
        try:
            proc = info.context['srmng'].get_by_id(id)
            data = proc.select_device(devNum)
            return Session(**data)
        except:
            raise GraphQLError('Error selecting device')

class CreateSession(graphene.Mutation):
    Output = Session
    async def mutate(self, info:graphene.ResolveInfo):
        try:
            data = info.context['srmng'].create_session()
            return Session(**data)
        except:
            raise GraphQLError('Error creating session')

class DeleteSession(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
    id = graphene.ID()
    async def mutate(self, info:graphene.ResolveInfo, id):
        try:
            info.context['srmng'].delete_session(id)
            return DeleteSession(id=id)
        except:
            raise GraphQLError("Error deleting session")
        
class SelectSamplerate(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        samplerate = graphene.String(required=True)
        
    id = graphene.ID()
    samplerate = graphene.String()
    
    async def mutate(self, info:graphene.ResolveInfo, id, samplerate):
        try:
            proc = info.context['srmng'].get_by_id(id)
            proc.select_samplerate(samplerate)
            return SelectSamplerate(id=id, samplerate=samplerate)
        except:
            raise GraphQLError("Error selecting samplerate")

class SelectSample(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        sample = graphene.String(required=True)
        
    id = graphene.ID()
    sample = graphene.String()
    
    async def mutate(self, info:graphene.ResolveInfo, id, sample):
        try:
            proc = info.context['srmng'].get_by_id(id)
            proc.select_sample(sample)
            return SelectSample(id=id, sample=sample)
        except:
            raise GraphQLError("Error selecting sample numbers")

class SrMutation(graphene.ObjectType):
    createSession = CreateSession.Field()
    deleteSession = DeleteSession.Field()
    selectDevice = SelectDevice.Field()
    selectSamplerate = SelectSamplerate.Field()
    selectSample = SelectSample.Field()
