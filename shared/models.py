"""
Shared models and data structures for the firewalld central management system.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, IPvAnyAddress
from enum import Enum


class AgentMode(str, Enum):
    PULL = "pull"
    PUSH = "push"


class AgentStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    PENDING = "pending"


class FirewallZone(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    INTERNAL = "internal"
    EXTERNAL = "external"
    DMZ = "dmz"
    WORK = "work"
    HOME = "home"
    TRUSTED = "trusted"
    DROP = "drop"
    BLOCK = "block"


class FirewallAction(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    DROP = "drop"


class RuleFamily(str, Enum):
    IPV4 = "ipv4"
    IPV6 = "ipv6"


# Agent Models
class AgentInfo(BaseModel):
    agent_id: str
    hostname: str
    ip_address: str
    mode: AgentMode
    status: AgentStatus
    last_seen: datetime
    version: str
    operating_system: str
    firewalld_version: str


class AgentRegistration(BaseModel):
    hostname: str
    ip_address: str
    mode: AgentMode
    certificate_request: str  # CSR for certificate generation


class AgentConfiguration(BaseModel):
    agent_id: str
    poll_interval: int = 30
    max_retries: int = 3
    timeout: int = 10


# Firewall Rule Models
class PortRule(BaseModel):
    port: str  # Can be single port or range (e.g., "80", "8000-8100")
    protocol: Literal["tcp", "udp", "sctp", "dccp"]


class ServiceRule(BaseModel):
    service: str  # Service name (e.g., "ssh", "http", "https")


class SourceRule(BaseModel):
    address: Optional[str] = None  # IP address or CIDR
    mac: Optional[str] = None  # MAC address
    ipset: Optional[str] = None  # IPSet name
    invert: bool = False


class DestinationRule(BaseModel):
    address: Optional[str] = None  # IP address or CIDR
    invert: bool = False


class ForwardPortRule(BaseModel):
    port: str
    protocol: Literal["tcp", "udp", "sctp", "dccp"]
    to_port: Optional[str] = None
    to_addr: Optional[str] = None


class MasqueradeRule(BaseModel):
    enabled: bool = True


class RichRule(BaseModel):
    family: Optional[RuleFamily] = None
    source: Optional[SourceRule] = None
    destination: Optional[DestinationRule] = None
    service: Optional[ServiceRule] = None
    port: Optional[PortRule] = None
    protocol: Optional[str] = None
    masquerade: Optional[MasqueradeRule] = None
    forward_port: Optional[ForwardPortRule] = None
    source_port: Optional[PortRule] = None
    icmp_block: Optional[str] = None
    icmp_type: Optional[str] = None
    action: Optional[FirewallAction] = None
    log: Optional[Dict[str, Any]] = None
    audit: Optional[bool] = None


class FirewallZoneConfig(BaseModel):
    zone: FirewallZone
    target: Optional[FirewallAction] = None
    interfaces: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    services: List[str] = Field(default_factory=list)
    ports: List[PortRule] = Field(default_factory=list)
    protocols: List[str] = Field(default_factory=list)
    masquerade: bool = False
    forward_ports: List[ForwardPortRule] = Field(default_factory=list)
    source_ports: List[PortRule] = Field(default_factory=list)
    icmp_blocks: List[str] = Field(default_factory=list)
    rich_rules: List[RichRule] = Field(default_factory=list)


class FirewallConfiguration(BaseModel):
    agent_id: str
    default_zone: FirewallZone = FirewallZone.PUBLIC
    zones: List[FirewallZoneConfig] = Field(default_factory=list)
    lockdown: bool = False
    panic_mode: bool = False


# API Request/Response Models
class ApiResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ApiError(BaseModel):
    error: str
    details: Optional[str] = None
    code: Optional[int] = None


class AgentCommand(BaseModel):
    command_id: str
    agent_id: str
    command_type: str
    parameters: Dict[str, Any]
    timeout: int = 30
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CommandResult(BaseModel):
    command_id: str
    agent_id: str
    success: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    executed_at: datetime = Field(default_factory=datetime.utcnow)


# User Management Models
class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    VIEWER = "viewer"


class UserPermission(BaseModel):
    user_id: str
    agent_ids: List[str] = Field(default_factory=list)  # Empty list = all agents
    role: UserRole
    can_modify: bool = True
    can_view: bool = True


# Web UI Models
class NetworkConnection(BaseModel):
    connection_id: str
    source_agent_id: str
    target_agent_id: str
    source_port: Optional[str] = None
    target_port: Optional[str] = None
    protocol: Optional[str] = None
    service: Optional[str] = None
    description: Optional[str] = None
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgentPosition(BaseModel):
    agent_id: str
    x: float
    y: float
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class WhiteboardState(BaseModel):
    agents: List[AgentPosition] = Field(default_factory=list)
    connections: List[NetworkConnection] = Field(default_factory=list)
    zoom: float = 1.0
    center_x: float = 0.0
    center_y: float = 0.0