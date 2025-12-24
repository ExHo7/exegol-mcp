# Exegol MCP Server

A Model Context Protocol (MCP) server that enables AI agents to interact with Exegol pentesting containers with **predefined workflows** for common pentesting tasks.

## Features

### Core Features
- ✅ Execute commands in Exegol containers (`exegol exec -v`)
- ✅ List available Exegol containers (`exegol info`)
- ✅ Health check and status monitoring
- ✅ 10-minute timeout for all command executions
- ✅ Concurrent execution support (5+ simultaneous commands)
- ✅ Structured JSON logging

### 🎯 Workflow Features (NEW!)
- ✅ **7 predefined pentesting workflows** ready to use
- ✅ **List workflows** with filtering by category, difficulty, or tags
- ✅ **Execute workflows** with automatic step sequencing
- ✅ Workflows for: Web recon, subdomain enumeration, port scanning, vulnerability scanning, and more
- ✅ Automatic error handling with continue-on-failure support

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
  command_execution: 600  # 10 minutes

logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR
  format: "json"  # json or text

mcp:
  server_name: "exegol-mcp-server"
  version: "0.1.0"

  # Compact mode: reduce token usage (recommended for Claude)
  compact_mode: true

sessions:
  # Persistent sessions: reuse bash sessions (more efficient)
  enabled: false
  idle_timeout: 300  # Close after 5 minutes of inactivity

parsing:
  # Auto-parse pentest tool outputs (nmap, subfinder, gobuster, etc.)
  auto_parse: true
```

### Configuration Options Explained

#### Compact Mode (`compact_mode: true`)
- **Purpose**: Reduce token usage in AI responses
- **Effect**: Shorter field names, omits verbose metadata
- **Recommended**: `true` for Claude interactions
- **Impact**: ~30% reduction in response size

#### Auto-Parsing (`auto_parse: true`)
- **Purpose**: Intelligently parse pentesting tool outputs
- **Supported tools**: nmap, subfinder, gobuster, nuclei, and more
- **Output**: Adds structured `parsed_output` field to responses
- **Benefit**: Makes results easier to analyze and process
- **Example**:
  ```json
  {
    "stdout": "...",
    "parsed_output": {
      "tool_detected": "nmap",
      "open_ports": ["22", "80", "443"],
      "services": {
        "22": "ssh",
        "80": "http",
        "443": "https"
      }
    }
  }
  ```

#### Persistent Sessions (`sessions.enabled: true`)
- **Purpose**: Reuse bash sessions across multiple commands
- **Benefit**: Faster execution, maintains environment state
- **Use case**: Multiple sequential commands on same container
- **Idle timeout**: Auto-close after 5 minutes of inactivity

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

## 🎯 Available MCP Tools

The server exposes **5 MCP tools**:

### Core Tools
1. **`exegol_exec`** - Execute a command in an Exegol container
2. **`exegol_list`** - List all available Exegol containers
3. **`exegol_status`** - Check MCP server health status

### Workflow Tools
4. **`list_workflows`** - List available predefined pentesting workflows
5. **`run_workflow`** - Execute a complete pentesting workflow

## 📋 Predefined Workflows

### Available Workflows

| Workflow | Category | Difficulty | Time | Description |
|----------|----------|------------|------|-------------|
| `recon_subdomain` | Recon | Easy | 10 min | Comprehensive subdomain enumeration with alive check |
| `port_scan_full` | Enumeration | Medium | 15 min | Full TCP port scan with service detection |
| `web_recon` | Web | Medium | 20 min | Web application reconnaissance (whatweb, gobuster, katana, finalrecon) |
| `vuln_scan_web` | Vulnerability Scan | Medium | 30 min | Web vulnerability scanning (nuclei, xsrfprobe) |
| `wordpress_scan` | Web | Easy | 15 min | WordPress vulnerability assessment (wpscan) |
| `network_sweep` | Network | Easy | 10 min | Network discovery and enumeration |
| `sql_injection_test` | Vulnerability Scan | Hard | 20 min | SQL injection vulnerability testing (sqlmap) |

### Workflow Usage Examples

#### 1. List All Available Workflows
Ask Claude:
```
List all available pentesting workflows
```

Claude will use the `list_workflows` MCP tool to show all 7 workflows with their details.

#### 2. Execute a Web Reconnaissance Workflow
Ask Claude:
```
Run the web_recon workflow on http://192.168.1.100
```

Claude will:
1. Use the `run_workflow` MCP tool
2. Specify workflow: `web_recon`
3. Set target: `http://192.168.1.100`
4. Execute all steps automatically:
   - Technology detection (whatweb)
   - Directory bruteforce (gobuster)
   - Web crawling (katana)
   - Comprehensive recon (finalrecon)
   - Display aggregated results

#### 3. Filter Workflows by Category
Ask Claude:
```
Show me all web pentesting workflows
```

Claude will use `list_workflows` with category filter to show only web-related workflows.

#### 4. Execute Subdomain Enumeration
Ask Claude:
```
Enumerate subdomains for example.com using the recon_subdomain workflow
```

Claude will:
1. Run subdomain discovery (subfinder)
2. Check which subdomains are alive (httpx)
3. Display summary of findings

### Workflow Parameters

Each workflow requires specific parameters:

| Workflow | Required Parameters | Optional Parameters |
|----------|-------------------|-------------------|
| `recon_subdomain` | `domain` | `output_dir` |
| `port_scan_full` | `target` | `rate` |
| `web_recon` | `url` | `wordlist` |
| `vuln_scan_web` | `url` | - |
| `wordpress_scan` | `url` | - |
| `network_sweep` | `network` | - |
| `sql_injection_test` | `url` | `data` |

### Real-World Example

**Scenario**: You want to perform reconnaissance on a web application.

**Ask Claude**:
```
I need to scan http://192.168.1.100:8080 for reconnaissance.
Use the web_recon workflow.
```

**Claude will**:
1. Detect technologies using whatweb
2. Bruteforce directories with gobuster
3. Crawl the website with katana
4. Run comprehensive reconnaissance with finalrecon
5. Show you all discovered endpoints, technologies, and potential attack vectors

**Results you'll get**:
- Detected web technologies (frameworks, libraries, versions)
- HTTP security headers analysis
- Discovered directories and files
- Crawled URLs
- JavaScript files and their contents
- Potential sensitive files exposed

### Workflow Features

- ✅ **Automatic step sequencing**: Workflows execute multiple commands in order
- ✅ **Error handling**: Steps can continue on failure if configured
- ✅ **Parameter validation**: Validates required parameters before execution
- ✅ **Detailed results**: Each step returns stdout, stderr, exit code, and execution time
- ✅ **Success tracking**: Know exactly which steps succeeded or failed

## Educational Use
This project is intended for educational purposes only. Always ensure you have permission to test any systems or networks.

## License
This project is licensed under the MIT License.