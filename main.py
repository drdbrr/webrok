#!/usr/bin/env python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.logger import logger
from starlette.endpoints import WebSocketEndpoint
from graphql.execution.executors.asyncio import AsyncioExecutor
from graphene import Schema
import uvicorn
import uvloop
import json

from pysigrok.srproc import SrProcessManager
from pysigrok.gqlapp import GraphQLAppExt
from pysigrok.srschema import SrQuery, SrMutation

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

srProcessManager = SrProcessManager()

app = FastAPI()
app.mount("/dist", StaticFiles(directory="dist"), name="dist")

@app.on_event("startup")
async def startup_event():
    try:
        srProcessManager.create_session()
    except:
        print('ERROR Starting')

#<link rel="icon" type="image/png" href="dist/favicon.ico" sizes="16x16" />

@app.get("/", include_in_schema=False, response_class=HTMLResponse)
async def root():
    return """
    <!DOCTYPE html>
    <html lang="en">
        <head>
            <meta charset="utf-8" />
        </head>
        <body>
            <noscript>You need to enable JavaScript to run this app.</noscript>
            <div id="root"></div>
            <script src="dist/bundle.js" type="text/javascript"></script>
        </body>
    </html>
    """
    
@app.websocket_route("/srsocket")
class SrWsSocket(WebSocketEndpoint):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #self.proc = None
        
    async def on_connect(self, websocket):
        logger.info(f"{bcolors.WARNING}WS connect{bcolors.ENDC}")
        await websocket.accept()
        #data = await websocket.receive_json()
        #pid = data['id']
        #self.proc = srProcessManager.get_by_pid(pid)
        #self.proc.ws_client = websocket
        #print('SELF:\n', self.scope.keys())
        #logger.info(f"{bcolors.WARNING}WS accepted pid: %s {bcolors.ENDC}", pid)
        
    async def on_receive(self, websocket, data):
        data = json.loads(data)
        print('WS data:', data)
        
        logger.debug(f'{bcolors.WARNING}WS data: %s{bcolors.ENDC}', data)
        #await self.proc.update_control_data(data)
        
    async def on_disconnect(self, websocket, close_code):
        #srProcessManager.delete_session(self.proc.sigrok.pid)
        logger.info(f"{bcolors.WARNING}WS disconnect{bcolors.ENDC}")

app.add_route("/sigrok", GraphQLAppExt(context={'srmng':srProcessManager}, graphiql=False, schema=Schema(query=SrQuery, mutation=SrMutation), executor=AsyncioExecutor()))
    
if __name__ == "__main__":
    uvloop.install()
    uvicorn.run("main:app", host="localhost", reload=True, port=3000, log_level="info")
