# MCP Server

The Speakr MCP server connects an AI assistant to your recordings through the [Model Context Protocol](https://modelcontextprotocol.io). With it, an assistant such as Claude can search what was said in your meetings, read transcripts and summaries, organize recordings, and upload new ones.

The server runs on your own machine, next to the assistant, and talks to your Speakr instance through the [REST API](api-reference.md). It is in the `mcp-server` folder of the repository. Speakr itself needs no change.

## Setup

### 1. Create an API token

Under **Account Settings** → **API Tokens**, create a token for the assistant (see [API Tokens](api-tokens.md)). The tools offered follow the token's scopes, so give it only what the assistant needs:

| Access | Scopes | The assistant can |
|--------|--------|-------------------|
| Read only | `read` | Search and read |
| Working assistant | `read`, `write`, `upload`, `process` | Also edit, upload and use the instance's models |

### 2. Build the image

```bash
git clone https://github.com/murtaza-nasir/speakr.git
docker build -t speakr-mcp speakr/mcp-server
```

Without Docker, install it with Python 3.11 or later: `pip install ./speakr/mcp-server` gives you the `speakr-mcp` command.

### 3. Add it to your assistant

=== "Claude Code"
    ```bash
    claude mcp add speakr \
      --env SPEAKR_URL=https://speakr.example.com \
      --env SPEAKR_API_TOKEN=YOUR_TOKEN \
      -- docker run -i --rm -e SPEAKR_URL -e SPEAKR_API_TOKEN speakr-mcp
    ```

=== "Other MCP clients"
    Most clients take a JSON configuration like this one (for Claude Desktop, `claude_desktop_config.json`):

    ```json
    {
      "mcpServers": {
        "speakr": {
          "command": "docker",
          "args": ["run", "-i", "--rm", "-e", "SPEAKR_URL", "-e", "SPEAKR_API_TOKEN", "speakr-mcp"],
          "env": {
            "SPEAKR_URL": "https://speakr.example.com",
            "SPEAKR_API_TOKEN": "YOUR_TOKEN"
          }
        }
      }
    }
    ```

If Speakr runs in Docker on the same machine, use `http://host.docker.internal:8899` as the address.

To check the connection, ask the assistant to call `get_connection_info`.

## Settings

| Variable | Required | Meaning |
|----------|----------|---------|
| `SPEAKR_URL` | yes | Address of your Speakr instance |
| `SPEAKR_API_TOKEN` | yes | The API token |
| `SPEAKR_MCP_SCOPES` | no | Comma-separated scopes to offer tools for. Default: `read,write,upload,process` |

A tool is offered only if its scope is in `SPEAKR_MCP_SCOPES` and the token has it.

## Tools

| Scope | Tools |
|-------|-------|
| any | `get_connection_info` |
| `read` | `search_recordings`, `list_recordings`, `get_recording`, `get_transcript`, `get_summary`, `get_notes`, `get_recording_status`, `get_recording_events`, `get_recording_speakers`, `list_tags`, `list_folders`, `list_speakers`, `get_current_user`, `get_stats`, `get_transcription_options` |
| `write` | `update_recording`, `add_recording_tags`, `remove_recording_tag`, `assign_speakers`, `create_tag`, `update_tag`, `create_folder`, `update_folder`, `create_speaker`, `update_speaker` |
| `upload` | `upload_recording` |
| `process` | `transcribe_recording`, `summarize_recording`, `regenerate_title`, `identify_speakers`, `chat_with_recording`, `inquire` |
| `share` | `create_share_link`, `list_share_links`, `revoke_share_link` |
| `delete` | `delete_recording`, `delete_recording_audio`, `delete_tag`, `delete_folder`, `delete_speaker` |

`share` and `delete` are off by default, also with a full-access token. See [Security](#security).

### Long transcripts

`get_transcript` returns one page at a time, 40,000 characters by default, because MCP clients limit the size of a tool result. While `next_offset` is not `null`, the assistant calls it again with that offset. To read only part of a recording, it can pass `start_seconds` and `end_seconds`.

### Uploading files

`upload_recording` takes a path on the machine where the server runs. In Docker, that machine is the container, so mount the folder with your recordings and use the path inside the container:

```bash
docker run -i --rm -e SPEAKR_URL -e SPEAKR_API_TOKEN -v /home/me/recordings:/recordings:ro speakr-mcp
```

The assistant then uploads `/recordings/meeting.mp3`.

## Security

!!! warning "Recorded text is not trustworthy"
    A transcript contains whatever was said in the recording, and a note or a shared recording contains what someone else wrote. An assistant reading that text can be misled by instructions placed in it, a technique called prompt injection. The server tells the assistant to treat this text as data, but that is not a guarantee.

For this reason:

- **`share` and `delete` must be turned on deliberately.** Add them to `SPEAKR_MCP_SCOPES` only when you need them, and keep your assistant's confirmation prompts on. These tools can publish a recording to anyone with the link, or destroy it for good.
- **Tools carry hints for your client.** Tools that replace or delete something are marked as destructive, so that a client can ask you first. `update_recording`, `transcribe_recording` and `summarize_recording` are among them, because they replace text that may have been edited by hand.
- **Use a dedicated, expiring token**, with only the scopes in the table above. Revoking it cuts off the assistant at once.
- **The models see your content.** Text the assistant reads is sent to the assistant's own model provider. `chat_with_recording`, `inquire` and `identify_speakers` also send it to the model configured on your instance.

## Limits

- The server speaks MCP over standard input and output, so it runs on the same machine as the assistant. It cannot be added as a remote connector by URL.
- Webhooks, account settings, audio download and the changes feed have no tools. Use the [REST API](api-reference.md) for these.
- The [rate limits](api-reference.md#rate-limits) of the API apply. Calls that use a model share the limit of 10 requests per minute per endpoint.

## Troubleshooting

| Message | Cause |
|---------|-------|
| `The token in SPEAKR_API_TOKEN is missing, expired or revoked` | Create a new token. The server does not start with a token Speakr refuses. |
| `Cannot reach Speakr at ...` | Check `SPEAKR_URL`. From inside a container, `localhost` is the container itself. |
| `Speakr redirected the request to ...` | Set `SPEAKR_URL` to that address, for example with `https://`. |
| `No file at ...` | The path must exist where the server runs. See [Uploading files](#uploading-files). |
| A tool you expected is missing | The token or `SPEAKR_MCP_SCOPES` lacks its scope. `get_connection_info` lists both. |

---

Next: [API Reference](api-reference.md)
