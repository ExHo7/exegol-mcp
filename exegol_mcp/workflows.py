"""Predefined pentest workflows for common tasks."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class WorkflowDifficulty(str, Enum):
    """Workflow difficulty levels."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class WorkflowCategory(str, Enum):
    """Workflow categories."""

    RECON = "recon"
    ENUMERATION = "enumeration"
    VULNERABILITY_SCAN = "vulnerability_scan"
    EXPLOITATION = "exploitation"
    POST_EXPLOITATION = "post_exploitation"
    WEB = "web"
    NETWORK = "network"


@dataclass
class WorkflowStep:
    """A single step in a workflow."""

    name: str
    command_template: str
    description: str = ""
    required_params: List[str] = field(default_factory=list)
    optional_params: List[str] = field(default_factory=list)
    continue_on_failure: bool = False

    def render(self, params: Dict[str, str]) -> str:
        """Render command with parameters.

        Args:
            params: Dictionary of parameter values

        Returns:
            Rendered command string

        Raises:
            ValueError: If required parameters are missing
        """
        # Check required parameters
        missing = [p for p in self.required_params if p not in params]
        if missing:
            raise ValueError(f"Missing required parameters: {', '.join(missing)}")

        # Render command
        return self.command_template.format(**params)


@dataclass
class Workflow:
    """A complete pentest workflow."""

    name: str
    description: str
    category: WorkflowCategory
    difficulty: WorkflowDifficulty
    steps: List[WorkflowStep]
    required_params: List[str] = field(default_factory=list)
    optional_params: List[str] = field(default_factory=list)
    estimated_time_minutes: int = 5
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "difficulty": self.difficulty.value,
            "required_params": self.required_params,
            "optional_params": self.optional_params,
            "estimated_time_minutes": self.estimated_time_minutes,
            "tags": self.tags,
            "steps": [
                {
                    "name": step.name,
                    "description": step.description,
                    "required_params": step.required_params,
                    "optional_params": step.optional_params,
                }
                for step in self.steps
            ],
        }


# ============================================================================
# PREDEFINED WORKFLOWS
# ============================================================================

WORKFLOWS = {
    "recon_subdomain": Workflow(
        name="recon_subdomain",
        description="Comprehensive subdomain enumeration and alive check",
        category=WorkflowCategory.RECON,
        difficulty=WorkflowDifficulty.EASY,
        required_params=["domain"],
        optional_params=["output_dir"],
        estimated_time_minutes=10,
        tags=["recon", "subdomain", "enumeration"],
        steps=[
            WorkflowStep(
                name="Subdomain Discovery",
                command_template="subfinder -d {domain} -silent -o /workspace/{domain}/subdomains.txt",
                description="Find subdomains using subfinder",
                required_params=["domain"],
            ),
            WorkflowStep(
                name="Alive Check",
                command_template="cat /workspace/{domain}/subdomains.txt | httpx -silent -o /workspace/{domain}/live_subs.txt",
                description="Check which subdomains are alive",
                required_params=["domain"],
                continue_on_failure=True,
            ),
            WorkflowStep(
                name="Display Results",
                command_template="echo 'Found:' && wc -l /workspace/{domain}/subdomains.txt && echo 'Alive:' && wc -l /workspace/{domain}/live_subs.txt && cat /workspace/{domain}/live_subs.txt",
                description="Show summary of findings",
                required_params=["domain"],
            ),
        ],
    ),
    "port_scan_full": Workflow(
        name="port_scan_full",
        description="Full TCP port scan with service detection",
        category=WorkflowCategory.ENUMERATION,
        difficulty=WorkflowDifficulty.MEDIUM,
        required_params=["target"],
        optional_params=["rate"],
        estimated_time_minutes=15,
        tags=["nmap", "port_scan", "enumeration"],
        steps=[
            WorkflowStep(
                name="Fast Port Discovery",
                command_template="nmap -p- --min-rate {rate} {target} -oN /workspace/{target}/nmap_all_ports.txt",
                description="Quickly find all open ports",
                required_params=["target"],
                optional_params=["rate"],
            ),
            WorkflowStep(
                name="Service Detection",
                command_template="nmap -p $(grep -oP '\\d+/open' /workspace/{target}/nmap_all_ports.txt | cut -d'/' -f1 | tr '\\n' ',') -sV -sC {target} -oN /workspace/{target}/nmap_services.txt",
                description="Detect services on open ports",
                required_params=["target"],
                continue_on_failure=True,
            ),
            WorkflowStep(
                name="Display Results",
                command_template="cat /workspace/{target}/nmap_services.txt | grep -E '(^[0-9]|open)'",
                description="Show discovered services",
                required_params=[],
            ),
        ],
    ),
    "web_recon": Workflow(
        name="web_recon",
        description="Web application reconnaissance workflow",
        category=WorkflowCategory.WEB,
        difficulty=WorkflowDifficulty.MEDIUM,
        required_params=["url"],
        optional_params=["wordlist"],
        estimated_time_minutes=20,
        tags=["web", "recon", "directory_bruteforce"],
        steps=[
            WorkflowStep(
                name="Technology Detection",
                command_template="whatweb -v {url}",
                description="Detect web technologies",
                required_params=["url"],
                continue_on_failure=True,
            ),
            WorkflowStep(
                name="Directory Bruteforce",
                command_template="gobuster dir -u {url} -w {wordlist} -o /workspace/{url}/gobuster.txt -q",
                description="Enumerate directories and files",
                required_params=["url"],
                optional_params=["wordlist"],
            ),
            WorkflowStep(
                name="Web Crawling",
                command_template="katana -u {url} -d 4 -kf all -aff -fx -silent -o /workspace/{url}/crawl.txt",
                description="Crawl the website",
                required_params=["url"],
                continue_on_failure=True,
            ),
            WorkflowStep(
                name="Final recon",
                command_template="finalrecon.py --full --url {url} -nb -cd /workspace/{url}/finalrecon",
                description="Run FinalRecon for comprehensive web recon",
                required_params=["url"],
                continue_on_failure=True,
            ),
            WorkflowStep(
                name="Display Results",
                command_template="echo '=== Directories ===' && cat /workspace/{url}/gobuster.txt && echo '\\n=== Crawled URLs ===' && wc -l /workspace/{url}/crawl.txt && echo '\\n=== FinalRecon Paths ===' && cat /workspace/{url}/finalrecon/paths.txt",
                description="Show discovered paths",
                required_params=[],
            ),
        ],
    ),
    "vuln_scan_web": Workflow(
        name="vuln_scan_web",
        description="Web vulnerability scanning workflow",
        category=WorkflowCategory.VULNERABILITY_SCAN,
        difficulty=WorkflowDifficulty.MEDIUM,
        required_params=["url"],
        estimated_time_minutes=30,
        tags=["vulnerability", "web", "nuclei"],
        steps=[
            WorkflowStep(
                name="Nuclei Scan",
                command_template="nuclei -u {url} -t /root/nuclei-templates/ -o /workspace/{url}/nuclei.txt",
                description="Run Nuclei template-based scanning",
                required_params=["url"],
                continue_on_failure=True,
            ),
            WorkflowStep(
                name="Xsrf Probe",
                command_template="xsrfprobe -u {url} -o /workspace/{url}/xsrf.txt",
                description="Check for XSRF vulnerabilities",
                required_params=["url"],
                continue_on_failure=True,
            ),
            WorkflowStep(
                name="Display Results",
                command_template="echo '=== Nuclei Findings ===' && cat /workspace/{url}/nuclei.txt | head -20",
                description="Show vulnerability findings",
                required_params=[],
            ),
        ],
    ),
    "wordpress_scan": Workflow(
        name="wordpress_scan",
        description="WordPress vulnerability assessment",
        category=WorkflowCategory.WEB,
        difficulty=WorkflowDifficulty.EASY,
        required_params=["url"],
        estimated_time_minutes=15,
        tags=["wordpress", "cms", "vulnerability"],
        steps=[
            WorkflowStep(
                name="WPScan Enumeration",
                command_template="wpscan --url {url} --enumerate p,t,u --random-user-agent -o /workspace/{url}/wpscan.txt",
                description="Enumerate plugins, themes, and users",
                required_params=["url"],
            ),
            WorkflowStep(
                name="Display Results",
                command_template="cat /workspace/{url}/wpscan.txt | grep -E '(\\[!\\]|\\[+\\])' | head -30",
                description="Show WPScan findings",
                required_params=[],
            ),
        ],
    ),
    "network_sweep": Workflow(
        name="network_sweep",
        description="Network discovery and enumeration",
        category=WorkflowCategory.NETWORK,
        difficulty=WorkflowDifficulty.EASY,
        required_params=["network"],
        estimated_time_minutes=10,
        tags=["network", "discovery", "enumeration"],
        steps=[
            WorkflowStep(
                name="Ping Sweep",
                command_template="nmap -sn {network} -oN /workspace/{network}/ping_sweep.txt",
                description="Discover alive hosts",
                required_params=["network"],
            ),
            WorkflowStep(
                name="Quick Port Scan",
                command_template="nmap -F $(grep 'Nmap scan report' /workspace/{network}/ping_sweep.txt | awk '{{print $NF}}' | tr -d '()') -oN /workspace/{network}/quick_scan.txt",
                description="Scan common ports on discovered hosts",
                required_params=[],
                continue_on_failure=True,
            ),
            WorkflowStep(
                name="Display Results",
                command_template="cat /workspace/{network}/quick_scan.txt | grep -E '(Nmap scan|open)'",
                description="Show discovered hosts and open ports",
                required_params=[],
            ),
        ],
    ),
    "sql_injection_test": Workflow(
        name="sql_injection_test",
        description="SQL injection vulnerability testing",
        category=WorkflowCategory.VULNERABILITY_SCAN,
        difficulty=WorkflowDifficulty.HARD,
        required_params=["url"],
        optional_params=["data"],
        estimated_time_minutes=20,
        tags=["sql_injection", "web", "sqlmap"],
        steps=[
            WorkflowStep(
                name="SQLMap Quick Test",
                command_template="sqlmap -u '{url}' --batch --smart --level=2 --risk=2 -o /workspace/{network}/sqlmap.txt",
                description="Test for SQL injection vulnerabilities",
                required_params=["url"],
            ),
            WorkflowStep(
                name="Database Enumeration",
                command_template="sqlmap -u '{url}' --batch --dbs -o /workspace/{network}/sqlmap_dbs.txt",
                description="Enumerate databases if vulnerable",
                required_params=["url"],
                continue_on_failure=True,
            ),
            WorkflowStep(
                name="Display Results",
                command_template="cat /workspace/{network}/sqlmap.txt | grep -E '(vulnerable|Parameter|injection)'",
                description="Show SQL injection findings",
                required_params=[],
            ),
        ],
    ),
}


class WorkflowManager:
    """Manage pentest workflows."""

    @staticmethod
    def list_workflows(
        category: Optional[WorkflowCategory] = None,
        difficulty: Optional[WorkflowDifficulty] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Workflow]:
        """
        List available workflows with optional filtering.

        Args:
            category: Filter by category
            difficulty: Filter by difficulty
            tags: Filter by tags (any match)

        Returns:
            List of matching workflows
        """
        workflows = list(WORKFLOWS.values())

        if category:
            workflows = [w for w in workflows if w.category == category]

        if difficulty:
            workflows = [w for w in workflows if w.difficulty == difficulty]

        if tags:
            workflows = [
                w for w in workflows if any(tag in w.tags for tag in tags)
            ]

        return workflows

    @staticmethod
    def get_workflow(name: str) -> Optional[Workflow]:
        """
        Get workflow by name.

        Args:
            name: Workflow name

        Returns:
            Workflow if found, None otherwise
        """
        return WORKFLOWS.get(name)

    @staticmethod
    def validate_params(workflow: Workflow, params: Dict[str, str]) -> List[str]:
        """
        Validate workflow parameters.

        Args:
            workflow: Workflow to validate
            params: Parameter values

        Returns:
            List of missing required parameters
        """
        return [
            p for p in workflow.required_params if p not in params or not params[p]
        ]
