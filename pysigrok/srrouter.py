from fastapi import APIRouter, Request
from typing import Optional
from fastapi.responses import HTMLResponse, RedirectResponse

from pysigrok.srprocmng import srMng
from pysigrok.srschema import srSchema
from pysigrok.srwsendpoint import SrWsEndpoint

from ariadne.asgi import GraphQL

srRouter = APIRouter()

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

@srRouter.get("/", include_in_schema=False)
async def index(request: Request, sid: Optional[str] = None):
    if sid in srMng._procs:
        return HTMLResponse(HTML_ROOT)
    else:
        proc = list(srMng._procs.values())[0]
        return RedirectResponse(url=f'/?sid={proc._id}') 
 
srRouter.add_route("/sigrok", GraphQL(srSchema, root_value=srMng, introspection = True, debug = True))
srRouter.add_websocket_route(path='/srsocket', endpoint=SrWsEndpoint)
