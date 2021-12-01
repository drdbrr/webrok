#!/usr/bin/python
import uvicorn
import uvloop
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pysigrok.srrouter import srRouter, Sigrok404
from config import cnf
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.cors import CORSMiddleware

origins = [
    "http://localhost",
    "http://localhost:5000",
    "https://localhost",
    "https://localhost:5000",
]

app = FastAPI(title = cnf.TITLE, description = cnf.DESCRIPTION, version = cnf.VERSION, contact = cnf.CONTACT.dict(), exception_handlers={ 404: Sigrok404 })
app.mount("/dist", StaticFiles(directory="dist"), name="dist")

app.add_middleware(HTTPSRedirectMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(srRouter)
    
if __name__ == "__main__":
    uvloop.install()
    uvicorn.run("main:app", host=cnf.HOST, port=cnf.PORT, reload=cnf.RELOAD, debug = cnf.DEBUG, log_level=cnf.LOG_LEVEL, ssl_keyfile = cnf.SSL_KEY, ssl_certfile = cnf.SSL_CERT)
