"""The part of FastAPI that flet_web's server uses, on starlette alone: pydantic-core has no Android build."""
from starlette import status
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from fastapi import routing

__all__ = ["FastAPI", "HTTPException", "Request", "WebSocket", "WebSocketDisconnect", "status"]


class FastAPI(Starlette):
    def __init__(self, *, debug=False, routes=None, middleware=None, exception_handlers=None, lifespan=None, **_):
        super().__init__(debug=debug, routes=routes, middleware=middleware,
                         exception_handlers=exception_handlers, lifespan=lifespan)

    def websocket(self, path):
        def add(handler):
            self.router.routes.append(WebSocketRoute(path, handler))
            return handler
        return add

    def _http(self, path, method):
        def add(handler):
            self.router.routes.append(Route(path, handler, methods=[method]))
            return handler
        return add

    def get(self, path, **_):
        return self._http(path, "GET")

    def put(self, path, **_):
        return self._http(path, "PUT")

    def post(self, path, **_):
        return self._http(path, "POST")
