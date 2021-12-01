from fastapi import APIRouter, Request, Response, HTTPException, Depends, Path
from typing import Optional
from fastapi.responses import HTMLResponse, RedirectResponse

from pysigrok.srprocmng import srMng, SrProcessManager, SrProtocol
from pysigrok.srschema import srSchema
from pysigrok.srwsendpoint import SrWsEndpoint

from ariadne.asgi import GraphQL



#Resolves session instance by query_params
async def session_param_handler(req):
    data = await req.json()
    
    extParam = data['extensions']['srExt'][0]
    if extParam in queryParamsHandlers:
        return queryParamsHandlers[extParam]
    
    else: 
        for key, val in req.query_params.items():
            if key in queryParamsHandlers:
                return queryParamsHandlers[key](val)


#Resolves handlers by path param
queryParamsHandlers = { 'sid': lambda sid: srMng.get_proc(sid), 'srmng': srMng }


async def start():
    try:
        await srMng.create_proc()
    except Exception as e:
        print('Can not create Sigrok session ', e)

srRouter = APIRouter(on_startup = [start])

async def Sigrok404(request, exc):
    proc = srMng.get_proc()
    return RedirectResponse(url=f'/sigrok?sid={proc.sid}')


HTML_ROOT = b"""
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
        
async def verify_sid(sid: str = None ):
    if not srMng.sid_exists(sid):
        raise HTTPException(status_code=404, detail="Sid not found")


@srRouter.get("/sigrok", include_in_schema=False)
async def index(sid: str = Depends(verify_sid)):
    return HTMLResponse(HTML_ROOT)

#async def get_ctx(request):
    ##data = await request.json()
    #path = request['path']
    #result = pathsHandlers[path](request)
    #return result
    

async def root_resolver(ctx, doc):
    req = ctx['request']
    result = await session_param_handler(req)
    return result
    
    
srGql = GraphQL(srSchema, root_value = root_resolver, introspection = True, debug = True)
srRouter.add_route("/sigrok", srGql, methods=["POST"], include_in_schema=False)

srRouter.add_websocket_route('/srsocket', SrWsEndpoint)
