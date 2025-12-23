"""Intelligent parsing of pentest tool outputs."""

import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class ParsedOutput:
    """Structured representation of parsed tool output."""

    tool_detected: Optional[str] = None
    summary: str = ""
    structured_data: Dict[str, Any] = field(default_factory=dict)
    raw_output: str = ""
    parsing_successful: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tool_detected": self.tool_detected,
            "summary": self.summary,
            "structured_data": self.structured_data,
            "raw_output": self.raw_output,
            "parsing_successful": self.parsing_successful,
        }


class OutputParser:
    """Parse common pentest tool outputs to structured data."""

    @staticmethod
    def parse_nmap(output: str) -> Dict[str, Any]:
        """
        Parse nmap output to structured data.

        Args:
            output: Raw nmap output

        Returns:
            Dictionary with parsed nmap data
        """
        open_ports = []
        host_info = {}

        # Parse host information
        host_match = re.search(r"Nmap scan report for (.+)", output)
        if host_match:
            host_info["target"] = host_match.group(1).strip()

        # Parse open ports
        port_pattern = r"(\d+)/(tcp|udp)\s+(open|closed|filtered)\s+(\S+)"
        for match in re.finditer(port_pattern, output):
            port_num, protocol, state, service = match.groups()
            if state == "open":
                open_ports.append({
                    "port": int(port_num),
                    "protocol": protocol,
                    "state": state,
                    "service": service,
                })

        # Parse OS detection
        os_match = re.search(r"OS details: (.+)", output)
        if os_match:
            host_info["os"] = os_match.group(1).strip()

        return {
            "host_info": host_info,
            "open_ports": open_ports,
            "total_open": len(open_ports),
            "summary": f"Found {len(open_ports)} open ports on {host_info.get('target', 'target')}",
        }

    @staticmethod
    def parse_subfinder(output: str) -> Dict[str, Any]:
        """
        Parse subfinder output.

        Args:
            output: Raw subfinder output

        Returns:
            Dictionary with parsed subdomain data
        """
        # Subfinder outputs one subdomain per line
        subdomains = []
        for line in output.split("\n"):
            line = line.strip()
            if line and not line.startswith("[") and "." in line:
                subdomains.append(line)

        # Deduplicate and sort
        subdomains = sorted(list(set(subdomains)))

        return {
            "subdomains": subdomains,
            "total": len(subdomains),
            "summary": f"Found {len(subdomains)} unique subdomains",
        }

    @staticmethod
    def parse_gobuster(output: str) -> Dict[str, Any]:
        """
        Parse gobuster directory/file enumeration output.

        Args:
            output: Raw gobuster output

        Returns:
            Dictionary with parsed directory/file data
        """
        found_paths = []

        # Gobuster format: /path (Status: 200) [Size: 1234]
        pattern = r"(/\S+)\s+\(Status:\s+(\d+)\)(?:\s+\[Size:\s+(\d+)\])?"
        for match in re.finditer(pattern, output):
            path, status_code, size = match.groups()
            entry = {
                "path": path,
                "status_code": int(status_code),
            }
            if size:
                entry["size"] = int(size)
            found_paths.append(entry)

        # Count by status code
        status_counts = {}
        for entry in found_paths:
            status = entry["status_code"]
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "paths": found_paths,
            "total": len(found_paths),
            "by_status": status_counts,
            "summary": f"Found {len(found_paths)} paths ({', '.join(f'{count} with status {status}' for status, count in status_counts.items())})",
        }

    @staticmethod
    def parse_httpx(output: str) -> Dict[str, Any]:
        """
        Parse httpx output (HTTP probing).

        Args:
            output: Raw httpx output

        Returns:
            Dictionary with parsed HTTP probe data
        """
        alive_hosts = []

        # httpx format: https://example.com [200] [Title]
        for line in output.split("\n"):
            line = line.strip()
            if line.startswith("http"):
                parts = line.split()
                if len(parts) >= 1:
                    url = parts[0]
                    status_match = re.search(r"\[(\d+)\]", line)
                    title_match = re.search(r"\[(.*?)\]$", line)

                    entry = {"url": url}
                    if status_match:
                        entry["status_code"] = int(status_match.group(1))
                    if title_match and title_match.group(1).isdigit() is False:
                        entry["title"] = title_match.group(1)

                    alive_hosts.append(entry)

        return {
            "alive_hosts": alive_hosts,
            "total": len(alive_hosts),
            "summary": f"Found {len(alive_hosts)} alive HTTP services",
        }

    @staticmethod
    def parse_nikto(output: str) -> Dict[str, Any]:
        """
        Parse nikto web vulnerability scanner output.

        Args:
            output: Raw nikto output

        Returns:
            Dictionary with parsed vulnerability data
        """
        findings = []
        target_info = {}

        # Parse target
        target_match = re.search(r"\+ Target IP:\s+(.+)", output)
        if target_match:
            target_info["ip"] = target_match.group(1).strip()

        target_host_match = re.search(r"\+ Target Hostname:\s+(.+)", output)
        if target_host_match:
            target_info["hostname"] = target_host_match.group(1).strip()

        # Parse findings (lines starting with +)
        for line in output.split("\n"):
            line = line.strip()
            if line.startswith("+ ") and "Target" not in line and "Start Time" not in line:
                findings.append(line[2:])  # Remove "+ " prefix

        return {
            "target_info": target_info,
            "findings": findings,
            "total_findings": len(findings),
            "summary": f"Found {len(findings)} potential issues on {target_info.get('hostname', 'target')}",
        }

    @staticmethod
    def parse_wpscan(output: str) -> Dict[str, Any]:
        """
        Parse WPScan WordPress vulnerability scanner output.

        Args:
            output: Raw wpscan output

        Returns:
            Dictionary with parsed WordPress data
        """
        vulnerabilities = []
        plugins = []
        themes = []

        # Parse vulnerabilities
        vuln_pattern = r"\[!\] Title: (.+)"
        for match in re.finditer(vuln_pattern, output):
            vulnerabilities.append(match.group(1).strip())

        # Parse plugins
        plugin_pattern = r"\[i\] Plugin\(s\) Identified: (.+)"
        for match in re.finditer(plugin_pattern, output):
            plugins.append(match.group(1).strip())

        # Parse themes
        theme_pattern = r"\[i\] Theme\(s\) Identified: (.+)"
        for match in re.finditer(theme_pattern, output):
            themes.append(match.group(1).strip())

        return {
            "vulnerabilities": vulnerabilities,
            "plugins": plugins,
            "themes": themes,
            "total_vulnerabilities": len(vulnerabilities),
            "summary": f"Found {len(vulnerabilities)} vulnerabilities, {len(plugins)} plugins, {len(themes)} themes",
        }

    @staticmethod
    def parse_sqlmap(output: str) -> Dict[str, Any]:
        """
        Parse sqlmap SQL injection testing output.

        Args:
            output: Raw sqlmap output

        Returns:
            Dictionary with parsed SQL injection data
        """
        vulnerabilities = []
        database_info = {}

        # Parse injections found
        if "sqlmap identified the following injection point" in output:
            vuln_type_pattern = r"Type: (.+)"
            for match in re.finditer(vuln_type_pattern, output):
                vulnerabilities.append(match.group(1).strip())

        # Parse database information
        db_match = re.search(r"web application technology: (.+)", output, re.IGNORECASE)
        if db_match:
            database_info["technology"] = db_match.group(1).strip()

        backend_match = re.search(r"back-end DBMS: (.+)", output, re.IGNORECASE)
        if backend_match:
            database_info["dbms"] = backend_match.group(1).strip()

        return {
            "vulnerabilities": list(set(vulnerabilities)),  # Deduplicate
            "database_info": database_info,
            "is_vulnerable": len(vulnerabilities) > 0,
            "summary": f"Found {len(set(vulnerabilities))} SQL injection types" if vulnerabilities else "No SQL injections found",
        }

    @staticmethod
    def detect_tool(output: str, command: str = "") -> Optional[str]:
        """
        Detect which pentesting tool generated the output.

        Args:
            output: Tool output
            command: Original command executed

        Returns:
            Tool name if detected, None otherwise
        """
        # Check command first
        command_lower = command.lower()
        tool_commands = {
            "nmap": "nmap",
            "subfinder": "subfinder",
            "gobuster": "gobuster",
            "ffuf": "ffuf",
            "httpx": "httpx",
            "nikto": "nikto",
            "wpscan": "wpscan",
            "sqlmap": "sqlmap",
            "masscan": "masscan",
            "nuclei": "nuclei",
        }

        for tool, cmd in tool_commands.items():
            if cmd in command_lower:
                return tool

        # Check output signatures
        output_lower = output.lower()
        if "nmap scan report" in output_lower:
            return "nmap"
        elif "wpscan" in output_lower and "wordpress" in output_lower:
            return "wpscan"
        elif "sqlmap" in output_lower:
            return "sqlmap"
        elif "nikto" in output_lower:
            return "nikto"
        elif "gobuster" in output_lower:
            return "gobuster"

        return None

    @staticmethod
    def auto_parse(command: str, output: str) -> ParsedOutput:
        """
        Automatically parse output based on detected tool.

        Args:
            command: Original command
            output: Command output

        Returns:
            ParsedOutput with structured data
        """
        tool = OutputParser.detect_tool(output, command)

        if not tool:
            return ParsedOutput(
                tool_detected=None,
                summary="No known tool detected",
                raw_output=output,
                parsing_successful=False,
            )

        # Parse based on tool
        parsers = {
            "nmap": OutputParser.parse_nmap,
            "subfinder": OutputParser.parse_subfinder,
            "gobuster": OutputParser.parse_gobuster,
            "httpx": OutputParser.parse_httpx,
            "nikto": OutputParser.parse_nikto,
            "wpscan": OutputParser.parse_wpscan,
            "sqlmap": OutputParser.parse_sqlmap,
        }

        parser = parsers.get(tool)
        if not parser:
            return ParsedOutput(
                tool_detected=tool,
                summary=f"Detected {tool} but no parser available",
                raw_output=output,
                parsing_successful=False,
            )

        try:
            structured_data = parser(output)
            return ParsedOutput(
                tool_detected=tool,
                summary=structured_data.get("summary", ""),
                structured_data=structured_data,
                raw_output=output,
                parsing_successful=True,
            )
        except Exception as e:
            return ParsedOutput(
                tool_detected=tool,
                summary=f"Parsing failed: {str(e)}",
                raw_output=output,
                parsing_successful=False,
            )
