#!/usr/bin/env python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.logger import logger
from starlette.endpoints import WebSocketEndpoint
from starlette.routing import WebSocketRoute
from starlette.types import ASGIApp, Receive, Scope, Send
from graphql.execution.executors.asyncio import AsyncioExecutor
from graphene import Schema
import uvicorn
import uvloop
import json

from pysigrok.srproc import SrProcessManager
from pysigrok.gqlapp import GraphQLAppExt
from pysigrok.srschema import SrQuery, SrMutation
from pysigrok.srwsendpoint import SrWsEndpoint

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
        
routes=[WebSocketRoute('/srsocket', SrWsEndpoint)]

app = FastAPI(routes=routes)
app.mount("/dist", StaticFiles(directory="dist"), name="dist")

class SrMngMiddleware:
    def __init__(self, app: ASGIApp):
        self._app = app
        self.srmng = srProcessManager

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "websocket":
            scope["srmng"] = self.srmng
        await self._app(scope, receive, send)

app.add_middleware(SrMngMiddleware)

@app.on_event("startup")
async def startup_event():
    try:
        srProcessManager.create_session()
    except:
        print('ERROR Starting')

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

app.add_route("/sigrok", GraphQLAppExt(context={'srmng':srProcessManager}, graphiql=False, schema=Schema(query=SrQuery, mutation=SrMutation), executor=AsyncioExecutor()))
    
if __name__ == "__main__":
    uvloop.install()
    uvicorn.run("main:app", host="localhost", reload=True, port=3000, log_level="info")
