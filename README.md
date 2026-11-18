# Grok meeting agent

A small Google Meet demo using Recall's native Grok audio integration and
[xAI's Voice Agent API](https://docs.x.ai/developers/model-capabilities/audio/speech-to-speech).
Recall connects meeting audio directly to Grok. A small authenticated
[MCP server](https://docs.x.ai/developers/model-capabilities/audio/speech-to-speech#remote-mcp-tools)
provides five meeting tools.

## Behavior

Address the agent as **“Assistant”** or **“grok demo”**, followed by a question or
command. The agent is instructed to join quietly and wait until addressed; the
app posts a short introduction in meeting chat. This address rule is a model
instruction, not an enforced audio filter.

| Action | Tool |
| --- | --- |
| Start or replace a screen share with a public webpage | `start_screenshare(url)` |
| Post text in meeting chat | `send_chat_message(message)` |
| Post the exact last accepted page URL | `send_current_page_link()` |
| Stop the screen share | `stop_screenshare()` |
| Leave the meeting | `leave_call()` |

Each accepted tool posts feedback in chat. Requested messages and links are their
own confirmation. Sharing a page does not automatically post its link.

## Requirements

- Python 3.12 and [uv](https://docs.astral.sh/uv/getting-started/installation/).
- A Recall workspace and its regional REST API key.
- An xAI API key with access to the Voice Agent API, saved in the Recall dashboard.
- An HTTPS tunnel, such as cloudflared, to expose the tool server.
- A Google account to host the meeting.

The sample does not require a separate avatar service. It has no mute or listening
controls because the native connection does not expose those controls to this app.

## Quickstart

### 1. Install dependencies

From the directory containing the downloaded `grok-meeting-agent` folder:

```sh
cd grok-meeting-agent
uv sync --locked
```

### 2. Configure Recall and Grok

In your Recall workspace, open **Agents → Grok** and save your xAI API key. Recall
uses that credential to connect the meeting to Grok; do not put it in this app's
local configuration.

Create the local configuration file:

```sh
cp .env.example .env
```

Fill in the root `.env`. It is ignored by Git and never sent to the browser.
Existing process environment variables take precedence.

| Variable | Value |
| --- | --- |
| `RECALL_API_KEY` | REST API key for the same Recall workspace where you configured Grok. |
| `RECALL_API_BASE_URL` | Matching regional API URL; the example uses `https://us-west-2.recall.ai/api/v1`. |
| `GROK_PUBLIC_URL` | The tunnel's HTTPS origin, without a path or trailing slash. |
| `GROK_VOICE` | xAI voice ID; the example uses `ara`. |
| `SESSION_TIMEOUT_SECONDS` | Overall session limit; defaults to `600` seconds. |

The sample uses `grok-voice-latest`. Restart the app and launch a new bot after
changing `.env`.

### 3. Start an HTTPS tunnel

With [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)
installed:

```sh
cloudflared tunnel --url http://127.0.0.1:7864
```

Copy the tunnel's HTTPS origin into `GROK_PUBLIC_URL` in `.env`. Keep this terminal
running.

Only tunnel the tool server on port **7864**. Keep the launcher on port **8004**
local. The public `/mcp` endpoint requires an expiring, per-meeting bearer token
created by the app. Audio travels directly between Recall and xAI, not through
this tunnel.

### 4. Start the app

Open another terminal in the repository root:

```sh
uv run --locked python -m app.web
```

Keep this process running alongside the tunnel, then open
[the launcher](http://127.0.0.1:8004).

### 5. Send the agent to a meeting

Create and join a meeting at [meet.new](https://meet.new/). Paste its URL into the
launcher and select **Send agent**, then admit **grok demo** once it enters the
waiting room.

### 6. Try the agent

Try these phrases:

| Try saying |
| --- |
| “Assistant, what is two plus two?” |
| “Assistant, show https://example.com.” |
| “Assistant, send the shared webpage link in chat.” |
| “Assistant, post Hello from the demo in chat.” |
| “Assistant, show https://www.recall.ai.” |
| “Assistant, send that link in chat.” |
| “Assistant, stop sharing.” |
| “Assistant, leave the meeting.” |

Check the meeting itself for the page, chat messages, and bot departure. A tool
result confirms Recall accepted a request; it does not prove the page rendered.

After the bot leaves, stop both terminal processes with Ctrl+C. Sessions expire
after 10 minutes by default. The app requests departure when a session expires
or the app shuts down. Start another bot to repeat the demo.

## Code map

| File | Responsibility |
| --- | --- |
| `app/web.py` | Serve the local form, create a bot, and run the two HTTP servers. |
| `app/templates/index.html` | One-field meeting launcher. |
| `app/config.py` | Load and validate local configuration. |
| `app/agent.py` | Grok instructions and native provider configuration. |
| `app/recall_client.py` | Recall HTTP requests and actionable errors. |
| `app/meeting_tools.py` | Five meeting actions and the last accepted page URL. |
| `app/sessions.py` | Per-meeting authorization, expiry, departure monitoring, and cleanup. |
| `app/tool_server.py` | Authenticated MCP tool definitions and dispatch. |

Recall creates a four-core Google Meet bot with `output_media.audio.kind = "grok"`.
The Grok session receives instructions, a voice, and a remote MCP tool descriptor.
The app keeps the bot ID returned by Create Bot on the server and scopes each
MCP token to that meeting. Tool callers cannot choose another bot ID.

Screen sharing uses Recall's [Output Media API](https://docs.recall.ai/reference/bot_output_media_create)
with a public webpage URL. The most recently accepted URL remains available after
sharing stops and is not replaced when a later request fails.

## Boundaries and troubleshooting

- If the bot joins but does not speak, check the xAI credentials in the same Recall
  workspace and the selected voice. Address it clearly as “Assistant.”
- If voice works but tools fail, check that the app and tunnel are both running,
  `GROK_PUBLIC_URL` matches the active tunnel, and the session has not expired.
- Native Grok controls speech detection and interruptions. Address-based behavior
  is instructed rather than enforced; this app does not provide mute, stop-listening,
  or avatar features.
- Chat messages are limited to 500 characters.
- Use public HTTPS webpages. The agent displays them but cannot read or interact
  with them; some sites may not load.
- Failed feedback messages do not undo an action or cause automatic retries.
- Recall recordings follow your workspace's retention settings; the app does not
  delete them or store meeting content locally.

This sample uses Recall's native Grok fields from the current Output Media schema.
The Recall MCP did not provide a dedicated Grok meeting-agent guide when this
sample was created; consult the current API reference and xAI documentation when
changing provider configuration.
