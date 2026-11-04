# Speakr MCP server

Connects an AI assistant to a Speakr instance through the [Model Context Protocol](https://modelcontextprotocol.io). See the [user guide](../docs/user-guide/mcp-server.md) for setup and the list of tools.

## Development

Everything runs in containers; nothing needs installing on the host.

```bash
# Unit tests
docker build --target test -t speakr-mcp-test mcp-server
docker run --rm speakr-mcp-test

# End to end: the real server over stdio against a real Speakr, with stand-ins
# for ASR and the language model. Publishes no ports.
docker compose -f mcp-server/tests/e2e/docker-compose.yml run --rm --build tests
docker compose -f mcp-server/tests/e2e/docker-compose.yml down -v
```

After a change to the dependencies in `pyproject.toml`, run `scripts/lock-requirements.sh`, which regenerates `requirements.lock` here together with Speakr's own lock files.

## Layout

| File | Purpose |
|------|---------|
| `src/speakr_mcp/config.py` | Settings and which scopes are offered |
| `src/speakr_mcp/client.py` | REST client; turns API errors into messages for the model |
| `src/speakr_mcp/transcript.py` | Paging of long transcripts |
| `src/speakr_mcp/server.py` | The tools, grouped by the token scope they need |
