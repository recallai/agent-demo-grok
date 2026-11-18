"""Bind expiring MCP access to one Recall bot and clean up its resources."""

import asyncio
import logging
import secrets
import time
from dataclasses import dataclass, field

from app.agent import INTRODUCTION, TOOL_NAMES, grok_config
from app.config import require_env, session_timeout, validate_agent_settings
from app.meeting_tools import MeetingState, MeetingTools, ToolError
from app.recall_client import RecallClient, RecallError

logger = logging.getLogger("meeting-demo")


@dataclass
class MeetingSession:
    client: RecallClient
    expires_at: float
    token: str = field(default_factory=lambda: secrets.token_urlsafe(32), repr=False)
    tools: MeetingTools | None = None
    ready: asyncio.Event = field(default_factory=asyncio.Event)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    monitor: asyncio.Task | None = None
    closed: bool = False


class MeetingSessions:
    def __init__(self):
        self._sessions: dict[str, MeetingSession] = {}

    def has_token(self, token: str) -> bool:
        session = self._sessions.get(token)
        return bool(session and not session.closed and time.monotonic() < session.expires_at)

    async def launch(self, meeting_url: str) -> str:
        validate_agent_settings()
        client = RecallClient(require_env("RECALL_API_KEY"), require_env("RECALL_API_BASE_URL"))
        await client.__aenter__()
        session = MeetingSession(client, time.monotonic() + session_timeout())
        self._sessions[session.token] = session
        try:
            # The provider can discover MCP tools before Create Bot returns its ID.
            async with session.lock:
                bot_id = await client.create_bot(meeting_url, grok_config(session.token))
                session.tools = MeetingTools(client, bot_id, MeetingState())
                session.ready.set()
            session.monitor = asyncio.create_task(self._watch_meeting(session))
            return bot_id
        except BaseException:
            await self.close(session, leave_bot=True)
            raise

    async def call_tool(self, token: str, name: str, arguments: dict) -> str:
        if not self.has_token(token):
            raise ToolError("The meeting session has ended.")
        if name not in TOOL_NAMES:
            raise ToolError("Unknown meeting tool.")
        expected = {"url"} if name == "start_screenshare" else (
            {"message"} if name == "send_chat_message" else set()
        )
        if set(arguments) != expected or any(not isinstance(v, str) for v in arguments.values()):
            raise ToolError("Provide only the documented text arguments for this tool.")
        session = self._sessions[token]
        try:
            async with asyncio.timeout(25):
                await session.ready.wait()
                async with session.lock:
                    if not self.has_token(token) or session.tools is None:
                        raise ToolError("The meeting session has ended.")
                    result = await getattr(session.tools, name)(**arguments)
                    leaving = session.tools.state.is_leaving
        except TimeoutError:
            raise ToolError(
                "Could not confirm the action. Check the meeting; do not retry automatically."
            ) from None
        if leaving:
            await self.close(session, leave_bot=False)
        return result

    async def _watch_meeting(self, session: MeetingSession) -> None:
        """Send the introduction once after admission; expire access after departure."""
        intro_attempted = False
        ended = False
        try:
            while time.monotonic() < session.expires_at:
                try:
                    async with session.lock:
                        if session.closed:
                            return
                        status = await session.client.get_bot_status(session.tools.bot_id)
                        if status in {"call_ended", "done", "fatal", "media_expired"}:
                            ended = True
                            return
                        if status in {"in_call_not_recording", "in_call_recording"} and not intro_attempted:
                            intro_attempted = True
                            try:
                                await session.client.send_chat_message(session.tools.bot_id, INTRODUCTION)
                            except RecallError:
                                logger.warning("Could not post the introduction; not retrying")
                except RecallError:
                    logger.warning("Could not read bot status; session expiration remains active")
                await asyncio.sleep(min(5, max(0, session.expires_at - time.monotonic())))
        finally:
            await self.close(session, leave_bot=not ended)

    async def close(self, session: MeetingSession, *, leave_bot: bool) -> None:
        async with session.lock:
            if session.closed:
                return
            session.closed = True
            self._sessions.pop(session.token, None)
            session.ready.set()
            monitor = session.monitor
            if monitor is not None and monitor is not asyncio.current_task():
                monitor.cancel()
            try:
                if leave_bot and session.tools and not session.tools.state.is_leaving:
                    try:
                        await session.client.leave_call(session.tools.bot_id)
                    except RecallError:
                        logger.warning("Could not confirm bot departure; check Recall's dashboard")
            finally:
                await session.client.aclose()
        if monitor is not None and monitor is not asyncio.current_task():
            await asyncio.gather(monitor, return_exceptions=True)

    async def close_all(self) -> None:
        await asyncio.gather(*(
            self.close(session, leave_bot=True) for session in list(self._sessions.values())
        ))


sessions = MeetingSessions()
