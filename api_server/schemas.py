import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class AgentStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    PENDING = "pending"
    ERROR = "error"


class AgentMode(str, Enum):
    PULL = "pull"
    PUSH = "push"


class CommandStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentRegistration(BaseModel):
    hostname: str
    ip_address: str
    operating_system: str
    version: str
    mode: AgentMode = AgentMode.PULL
    pull_interval: int = 300  # seconds
    certificate_request: Optional[str] = None


class AgentInfo(BaseModel):
    id: str
    hostname: str
    ip_address: str
    operating_system: str
    version: str
    mode: AgentMode
    status: AgentStatus
    last_seen: Optional[datetime] = None
    pull_interval: int = 300
    position_x: float = 0
    position_y: float = 0
    certificate_issued: bool = False
    created_at: datetime
    updated_at: datetime


class AgentCommand(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str
    command: str
    params: Dict[str, Any] = Field(default_factory=dict)
    status: CommandStatus = CommandStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class CommandRequest(BaseModel):
    command: str
    params: Dict[str, Any] = Field(default_factory=dict)


class CommandResponse(BaseModel):
    command_id: str
    status: CommandStatus
    message: str


class AgentConfigSync(BaseModel):
    agent_id: str
    config_hash: str
    last_sync: datetime
    pending_changes: bool = False


class FirewallRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str
    zone: str
    rule_type: str  # service, port, rich_rule, etc.
    rule_data: Dict[str, Any]
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AgentStatusUpdate(BaseModel):
    agent_id: str
    status: AgentStatus
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: Optional[Dict[str, Any]] = None


class WhiteboardState(BaseModel):
    center_x: float = 0
    center_y: float = 0
    zoom: float = 1.0
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class NetworkConnection(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_agent_id: str
    target_agent_id: str
    source_port: Optional[int] = None
    target_port: Optional[int] = None
    protocol: str = "tcp"
    description: Optional[str] = None
    color: str = "#007bff"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class APIError(BaseModel):
    error: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthCheck(BaseModel):
    status: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str
    database_connected: bool
    redis_connected: bool
    active_agents: int