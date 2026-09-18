# Talebrew MCP Server Setup

This lets an AI agent (Claude Desktop, Claude Code, or any other [MCP](https://modelcontextprotocol.io/) client) hand Talebrew a file to convert and check on it, without a human clicking through the GUI. Follow the steps below and you're done.

## Option A: the Windows installer's "Install MCP Server support" checkbox

If you're installing Talebrew from the `.msi` (rather than running from a source checkout), the installer wizard has an optional "Install MCP Server support" checkbox -- shown right after you pick an install directory, **unchecked by default** (most people installing Talebrew just want the desktop app). Check it and the installer adds a second, ready-to-run binary, `TalebrewMCP.exe`, alongside `Talebrew.exe` -- no `poetry install` needed.

It also drops a ready-to-paste config file, `talebrew_mcp_claude_config.json`, into the same install directory (`C:\Program Files\Talebrew\` by default), with `TalebrewMCP.exe`'s real installed path already filled in:

```json
{
  "mcpServers": {
    "talebrew": {
      "command": "C:\\Program Files\\Talebrew\\TalebrewMCP.exe"
    }
  }
}
```

Copy that straight into `claude_desktop_config.json` (see Option B, step 2, for where that file lives) or `.mcp.json`. If you installed Talebrew somewhere other than the default directory, edit the `command` path in the generated file to match -- the installer can't know your chosen path at the time it generates this file (see `RELEASING.md`'s "Installer: optional MCP Server feature" section for why), so it always fills in the default location.

Since `TalebrewMCP.exe` is a self-contained frozen binary (no Python/Poetry involved), you don't need `args` or `cwd` in the config the way Option B's `poetry run` command does.

## Option B: running from a source checkout

### 1. Install the MCP dependency group

The MCP server needs one extra package (`mcp`) that isn't part of Talebrew's normal runtime dependencies -- it's not bundled into the desktop `.msi` installer, since it's a developer/agent integration, not something every end user needs. From the repo root:

```
poetry install --with mcp
```

### 2. Point your MCP client at it

The server (`mcp_server.py`) speaks MCP over stdio: the client launches it as a subprocess and talks to it over stdin/stdout, so there's no port or URL to configure -- just the command to run it.

### Claude Desktop

Open (or create) `claude_desktop_config.json`:
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

Add a `talebrew` entry under `mcpServers`, using the **absolute path** to your Talebrew checkout:

```json
{
  "mcpServers": {
    "talebrew": {
      "command": "poetry",
      "args": ["run", "python", "mcp_server.py"],
      "cwd": "C:\\path\\to\\talebrew"
    }
  }
}
```

Restart Claude Desktop afterward. If `poetry` isn't on your `PATH` from Claude Desktop's point of view, use the full path to `poetry.exe` (or your virtualenv's `python.exe` directly, with `args: ["mcp_server.py"]`) instead of the bare `"poetry"` command.

### Claude Code

In your Talebrew checkout, create (or edit) `.mcp.json` at the repo root:

```json
{
  "mcpServers": {
    "talebrew": {
      "command": "poetry",
      "args": ["run", "python", "mcp_server.py"]
    }
  }
}
```

Claude Code runs `.mcp.json`-declared servers with that directory as the working directory automatically, so no `cwd` is needed here. Restart Claude Code (or run `/mcp` to reconnect) after saving.

### 3. Try it

Once connected, your agent has four tools: `list_supported_formats`, `convert_file`, `get_conversion_status`, and `list_conversions`. Example prompts:

- "Convert `~/Documents/mybook.epub` to audio using Piper, then tell me when it's done."
- "What audio formats can Talebrew convert to?" *(exercises `list_supported_formats`)*
- "List everything in my Talebrew Conversions library, with page and chapter counts."
- "Check on job `<job_id>` from that last conversion -- is it finished yet?"

## How it works, briefly

- `convert_file` starts a conversion on a background thread and returns immediately with a `job_id` -- a full book can take minutes (or, with Piper on some hardware, much longer; see the main [README](README.md#platform-notes)), so the tool call itself never blocks waiting for it.
- `get_conversion_status(job_id)` reads status from a small JSON file (`~/.texttoaudio/mcp_jobs.json`), not just server memory -- so it still works even if your MCP client restarts the server process between calls.
- `engine`/`voice`/`output_dir` are all optional on `convert_file`; omitted ones fall back to whatever Talebrew's own Settings currently has configured (`~/.texttoaudio/config.json`), the same as converting a file with no per-file override in the GUI.
- The server runs fully headless -- no GUI window opens, and it works whether or not Talebrew's desktop app is running.

## Troubleshooting

- **Client says the server failed to start (Option B)**: run `poetry run python mcp_server.py` directly from the repo root in a terminal. If that itself fails with `ModuleNotFoundError: No module named 'mcp'`, step 1 wasn't completed in that virtualenv.
- **Client says the server failed to start (Option A)**: run `TalebrewMCP.exe` directly from a terminal (e.g. `& "C:\Program Files\Talebrew\TalebrewMCP.exe"` in PowerShell) -- it should sit waiting for stdio input with no output and no window, which is correct; an MCP client talks to it, a human at a terminal won't see anything happen. If the file doesn't exist at all, the installer's "Install MCP Server support" checkbox wasn't checked -- rerun the installer (or `msiexec /passive` a fresh copy) and check it, or fall back to Option B.
- **A Piper conversion silently uses the system voice instead**: this matches the GUI's own fallback behavior -- Piper needs to be installed and the requested voice downloaded first (normally done from Talebrew's Settings drawer). Check the job's status output for a warning about it.
