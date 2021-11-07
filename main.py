#!/usr/bin/python

import uvicorn
import uvloop
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pysigrok.srrouter import srRouter

from pysigrok.srprocmng import srMng

app = FastAPI()
app.state.clients = []
#app.state.srmng = srMng

app.mount("/dist", StaticFiles(directory="dist"), name="dist")
app.include_router(srRouter)

@app.on_event("startup")
async def startup_event():
    try:
        await srMng.create_session()
    except Exception as e:
        print('App.startup: Can not create session ', e)
        
#@app.on_event("shutdown")
#async def shutdown_event():
    ##pids = get_pid('srproc')
    ##for pid in pids:
        ##kill(pid, 9)
    
    #for proc in srMng._procs.values():
        #proc.stop()
    
if __name__ == "__main__":
    uvloop.install()
    uvicorn.run("main:app", host="localhost", reload=True, port=3000, log_level="debug")
