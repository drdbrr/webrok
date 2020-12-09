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
    
class LogicChannel(graphene.ObjectType):
    name = graphene.String()
    #text = graphene.String()
    #type = graphene.String()
    #enabled = graphene.Int()
    #index = graphene.Int()
    #visible = graphene.Int()
    #traceHeight = graphene.Int()
    #positionY = graphene.Int()
    #pos = graphene.Int()
    #lineRef = graphene.Int()
    
class AnalogChannel(graphene.ObjectType):
    name = graphene.String()
    #text = graphene.String()
    #type = graphene.String()
    #enabled = graphene.Int()
    #index = graphene.Int()
    #visible = graphene.Int()
    #divHeight = graphene.Int()
    #negDivs = graphene.Int()
    #posDivs = graphene.Int()
    #divResolution = graphene.Int()
    #positionY = graphene.Int()
    #lineRef = graphene.Int()



class Session(graphene.ObjectType):
    id = graphene.ID()
    name = graphene.String(default_value='')
    sourcename = graphene.String(default_value='')
    samplerate = graphene.String(default_value ='')
    samplerates = graphene.List(graphene.String, default_value = [])
    sample = graphene.String(default_value = '')
    samples = graphene.List(graphene.String, default_value = [])
    logic = graphene.List(LogicChannel, default_value = [])
    analog = graphene.List(AnalogChannel, default_value = [])

#---------QUERIES---------#
class SrQuery(graphene.ObjectType):
    sessions = graphene.List(Session)
    session = graphene.Field(Session, id=graphene.ID(required=True)) #, devNum=graphene.Int(required=True))
    drivers = graphene.List(graphene.String, default_value = [])
    scanDevices = graphene.List(DeviceInfo, id=graphene.ID(required=True), drv=graphene.String(required=True))
    samplerate = graphene.Field(Samplerate, id=graphene.ID(required=True))
    
    sample = graphene.Field(Sample, id=graphene.ID(required=True))
    
    async def resolve_sample(self, info:graphene.ResolveInfo, id):
        proc = info.context['srmng'].get_by_id(id)
        data = proc.get_sample()
        print(data)
        return Sample(**data)
    
    async def resolve_samplerate(self, info:graphene.ResolveInfo, id):
        proc = info.context['srmng'].get_by_id(id)
        data = proc.get_samplerate()
        print(data)
        return Samplerate(**data)
    
    async def resolve_scanDevices(self, info:graphene.ResolveInfo, id, drv):
        proc = info.context['srmng'].get_by_id(id)
        data = proc.scan_devices(drv)#runcmd('get_scan', drv)
        #result = []
        #for item in data:
            #result.append(DeviceInfo(vendor = item['vendor'], model = item['model'], driverName = item['driverName'], connectionId = item['connectionId']))
        return [ DeviceInfo(**item) for item in data ]#result
    
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
        data = proc.get_params()
        #print('DATA:', data)
        #data['logic'] = [LogicChannel(name = 'L1')]
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
            #print('data', data)
            return Session(**data)#(id=id, name=proc.name, sourcename=proc.sourcename)
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
