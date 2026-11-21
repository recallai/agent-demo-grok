# Working on this sample

Keep this a small, runnable meeting agent demo with a local meeting-URL form.

- Launch `web_4_core` bots on Zoom, Google Meet, Microsoft Teams, and Webex.
- Use Recall's native Grok audio integration: `output_media.audio.kind = "grok"`.
  Grok receives meeting audio directly and calls this app's hosted MCP tools.
- Keep exactly five conversational tools: `start_screenshare`, `send_chat_message`,
  `send_current_page_link`, `stop_screenshare`, and `leave_call`.
- Require explicit participant requests in the agent instructions. Addressing the
  agent as `Assistant` or `grok demo` is a model instruction, not a deterministic
  audio filter. Do not promise mute, listening controls, or an avatar.
- Instruct the agent to join quietly and wait for addressed requests. Use Recall's
  `chat.on_bot_join` to post one short introduction on platforms with meeting chat.
- Each accepted tool posts feedback where chat is available. Requested text and
  links are their own feedback. Never repeat or undo an action because a feedback
  message failed.
- Show public HTTPS webpages without reading or interacting with them. Preserve
  the last accepted URL when a later share fails. Stop only the screen share.
- Post a departure message before leaving. Leaving removes only this bot.
- Keep the launcher local on port 8004. Expose only the authenticated MCP server
  on port 7864 through an HTTPS tunnel, at `/mcp`.
- Scope each expiring bearer token to a server-owned bot ID. Never accept a bot ID
  or Recall credentials from MCP tool arguments. Monitor departure, session expiry,
  and process shutdown, and clean up the session once.
- Configure xAI credentials in Recall Dashboard > Agents > Grok. The local app
  needs only the Recall key; never read or copy xAI keys from another project.
- Keep local credentials in the ignored root `.env` or process environment.
  `.env.example` contains placeholders only. Never log credentials, tokens, request
  bodies, or meeting content.
- Use Recall MCP documentation and official xAI docs to verify behavior. Record
  documentation gaps instead of inventing provider settings. Native Grok uses
  server-side VAD and hosted MCP tools, not a local audio-processing pipeline.
- Use concrete names, keep related logic together, and review files approaching
  300 lines. Separate provider configuration, meeting actions, HTTP, and lifecycle
  where doing so makes the code easier to understand.
- Do not add evaluator code, test harnesses, verification instrumentation, or
  reports to this repository. The user runs the meeting demo; verification stays
  outside the repository.
- Keep the README focused on one setup path and the five-action demonstration.
  Do not invent a clone URL before a remote repository exists.
- Report local checks separately from observed live meeting behavior.
