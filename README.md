# Exegol MCP Server

A Model Context Protocol (MCP) server that enables AI agents to interact with Exegol pentesting containers.

## Features

- ✅ Execute commands in Exegol containers (`exegol exec -v`)
- ✅ List available Exegol containers (`exegol info`)
- ✅ Health check and status monitoring
- ✅ 3-minute timeout for all command executions
- ✅ Concurrent execution support (5+ simultaneous commands)
- ✅ Structured JSON logging

## Prerequisites

- **Python 3.10+**
- **Exegol CLI** installed and accessible ([Exegol Installation](https://github.com/ThePorgs/Exegol))
- **Docker** running (required by Exegol)
- At least one Exegol container created

Verify prerequisites:
```bash
python3 --version  # Should be 3.10+
exegol --version   # Should show Exegol version
docker ps          # Should show Docker is running
exegol info        # Should list Exegol containers
```

## Installation

1. Clone or download this repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure the server:
```bash
# Edit config.yaml to set your Exegol path
vim config.yaml
```

## Configuration

Edit `config.yaml`:

```yaml
exegol:
  path: "exegol"  # or /usr/local/bin/exegol

timeout:
  command_execution: 180  # 3 minutes (fixed)

logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR
  format: "json"  # json or text
```

## Usage

### Run as MCP Server

```bash
python exegol_mcp.py
```

The server will start on stdio transport, ready for MCP client connections.

### Integrate with Claude Desktop

Add to `~/.config/claude/mcp.json` (Linux/Mac) or `%APPDATA%\Claude\mcp.json` (Windows):

```json
{
  "mcpServers": {
    "exegol": {
      "command": "python",
      "args": ["/absolute/path/to/exegol_mcp.py"]
    }
  }
}
```

Restart Claude Desktop, then try:
- "List available Exegol containers"
- "Execute 'whoami' in the pentest-box container"

### Integrate with CLaude Code 

```bash
claude mcp add --transport stdio exegol-mcp -- python /absolute/path/to/exegol_mcp.py
```

Then use in claude code:
```bash
/mcp
```
To check mcp status

## Educational Use
This project is intended for educational purposes only. Always ensure you have permission to test any systems or networks.

## License
This project is licensed under the MIT License.