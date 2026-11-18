"""Authenticated MCP tools for one Grok meeting, exposed through an HTTPS tunnel."""

from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError as MCPToolError
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import public_origin
from app.meeting_tools import ToolError
from app.sessions import sessions

server = MCPServer("Grok meeting tools", log_level="WARNING")
security = TransportSecuritySettings()


async def call_meeting_tool(ctx: Context, name: str, arguments: dict) -> str:
    """Use only the meeting token validated by the HTTP middleware."""
    request = ctx.request_context.request
    if not isinstance(request, Request):
        raise TypeError("Meeting tools require an authenticated HTTP request.")
    try:
        return await sessions.call_tool(request.state.meeting_token, name, arguments)
    except ToolError as error:
        # Expected action failures must reach Grok, not become a generic SDK crash.
        raise MCPToolError(str(error)) from None


@server.tool()
async def start_screenshare(url: str, ctx: Context) -> str:
    """Show a public HTTPS webpage only when a participant explicitly asks.

    This displays the page without reading it or posting its URL to chat.
    A new page replaces the current share. Do not invent an unspecified URL.
    """
    return await call_meeting_tool(ctx, "start_screenshare", {"url": url})


@server.tool()
async def send_chat_message(message: str, ctx: Context) -> str:
    """Post text to meeting chat only on an explicit request to send it.

    Use send_current_page_link for the currently selected page's exact URL.
    Discussing or showing a webpage does not authorize posting a message.
    """
    return await call_meeting_tool(ctx, "send_chat_message", {"message": message})


@server.tool()
async def send_current_page_link(ctx: Context) -> str:
    """Post the exact stored page URL only when explicitly asked to send its link."""
    return await call_meeting_tool(ctx, "send_current_page_link", {})


@server.tool()
async def stop_screenshare(ctx: Context) -> str:
    """Stop sharing the page when asked, keeping the agent's voice connected."""
    return await call_meeting_tool(ctx, "stop_screenshare", {})


@server.tool()
async def leave_call(ctx: Context) -> str:
    """Leave this meeting only when a participant explicitly asks the agent to leave.

    Removes only this bot, not other participants. The current session cannot
    rejoin afterward. Do not retry if the result is uncertain.
    """
    return await call_meeting_tool(ctx, "leave_call", {})


class MeetingTokenMiddleware:
    """Authenticate every MCP request before discovery or execution."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        if request.url.path != "/mcp":
            await JSONResponse({"error": "Not found"}, status_code=404)(
                scope, receive, send
            )
            return

        authorization = request.headers.getlist("authorization")
        scheme, _, token = (
            authorization[0].partition(" ") if len(authorization) == 1 else ("", "", "")
        )
        if scheme.lower() != "bearer" or not token or not sessions.has_token(token):
            await JSONResponse(
                {"error": "Unauthorized"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )(scope, receive, send)
            return

        request.state.meeting_token = token
        await self.app(scope, receive, send)


mcp_app = server.streamable_http_app(
    streamable_http_path="/mcp",
    stateless_http=True,
    json_response=True,
    max_request_body_size=64 * 1024,
    transport_security=security,
)


@asynccontextmanager
async def lifespan(app: Starlette):
    origin = public_origin()
    security.allowed_hosts = [
        "127.0.0.1",
        "127.0.0.1:*",
        "localhost",
        "localhost:*",
        urlsplit(origin).netloc,
    ]
    security.allowed_origins = ["http://127.0.0.1:*", "http://localhost:*", origin]
    async with server.session_manager.run():
        yield


tool_app = Starlette(routes=[Mount("/", app=mcp_app)], lifespan=lifespan)
tool_app.add_middleware(MeetingTokenMiddleware)
