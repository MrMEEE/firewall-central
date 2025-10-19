"""
Firewalld Manager - Handles all firewalld operations.
"""

import asyncio
import subprocess
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Any, Union
import re
import structlog

from shared.models import (
    FirewallConfiguration, FirewallZoneConfig, FirewallZone,
    PortRule, ServiceRule, RichRule, ForwardPortRule,
    SourceRule, DestinationRule, MasqueradeRule, FirewallAction, RuleFamily
)


class FirewalldManager:
    """Manages firewalld configuration through firewall-cmd."""
    
    def __init__(self):
        self.logger = structlog.get_logger("firewalld_manager")
    
    def is_available(self) -> bool:
        """Check if firewalld is available and running."""
        try:
            result = subprocess.run(
                ["firewall-cmd", "--state"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0 and "running" in result.stdout
        except Exception:
            return False
    
    def get_version(self) -> str:
        """Get firewalld version."""
        try:
            result = subprocess.run(
                ["firewall-cmd", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return "unknown"
        except Exception:
            return "unknown"
    
    async def run_command(self, command: List[str], timeout: int = 10) -> Dict[str, Any]:
        """Run a firewall-cmd command asynchronously."""
        try:
            self.logger.debug("Running firewall command", command=command)
            
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            result = {
                "returncode": process.returncode,
                "stdout": stdout.decode().strip(),
                "stderr": stderr.decode().strip(),
                "success": process.returncode == 0
            }
            
            if not result["success"]:
                self.logger.error("Firewall command failed",
                                command=command,
                                stderr=result["stderr"])
            
            return result
            
        except asyncio.TimeoutError:
            self.logger.error("Firewall command timed out", command=command)
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": "Command timed out",
                "success": False
            }
        except Exception as e:
            self.logger.error("Error running firewall command",
                            command=command,
                            error=str(e))
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "success": False
            }
    
    async def get_status(self) -> Dict[str, Any]:
        """Get current firewall status."""
        status = {}
        
        # Get basic state
        result = await self.run_command(["firewall-cmd", "--state"])
        status["running"] = result["success"]
        
        if not status["running"]:
            return status
        
        # Get default zone
        result = await self.run_command(["firewall-cmd", "--get-default-zone"])
        if result["success"]:
            status["default_zone"] = result["stdout"]
        
        # Get all zones
        result = await self.run_command(["firewall-cmd", "--get-zones"])
        if result["success"]:
            status["available_zones"] = result["stdout"].split()
        
        # Get active zones
        result = await self.run_command(["firewall-cmd", "--get-active-zones"])
        if result["success"]:
            status["active_zones"] = self._parse_active_zones(result["stdout"])
        
        # Get panic mode
        result = await self.run_command(["firewall-cmd", "--query-panic"])
        status["panic_mode"] = result["success"]
        
        # Get lockdown mode
        result = await self.run_command(["firewall-cmd", "--query-lockdown"])
        status["lockdown"] = result["success"]
        
        # Get zone configurations
        status["zones"] = {}
        for zone in status.get("available_zones", []):
            status["zones"][zone] = await self.get_zone_config(zone)
        
        return status
    
    def _parse_active_zones(self, output: str) -> Dict[str, List[str]]:
        """Parse active zones output."""
        active_zones = {}
        current_zone = None
        
        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            if line.endswith(':') or (line and not line.startswith(' ')):
                current_zone = line.rstrip(':')
                active_zones[current_zone] = []
            elif current_zone and line.startswith(' '):
                interfaces = line.strip().split()
                active_zones[current_zone].extend(interfaces)
        
        return active_zones
    
    async def get_zone_config(self, zone: str) -> Dict[str, Any]:
        """Get configuration for a specific zone."""
        config = {
            "zone": zone,
            "target": None,
            "interfaces": [],
            "sources": [],
            "services": [],
            "ports": [],
            "protocols": [],
            "masquerade": False,
            "forward_ports": [],
            "source_ports": [],
            "icmp_blocks": [],
            "rich_rules": []
        }
        
        # Get target
        result = await self.run_command(["firewall-cmd", "--zone", zone, "--get-target"])
        if result["success"] and result["stdout"] != "default":
            config["target"] = result["stdout"]
        
        # Get interfaces
        result = await self.run_command(["firewall-cmd", "--zone", zone, "--list-interfaces"])
        if result["success"] and result["stdout"]:
            config["interfaces"] = result["stdout"].split()
        
        # Get sources
        result = await self.run_command(["firewall-cmd", "--zone", zone, "--list-sources"])
        if result["success"] and result["stdout"]:
            config["sources"] = result["stdout"].split()
        
        # Get services
        result = await self.run_command(["firewall-cmd", "--zone", zone, "--list-services"])
        if result["success"] and result["stdout"]:
            config["services"] = result["stdout"].split()
        
        # Get ports
        result = await self.run_command(["firewall-cmd", "--zone", zone, "--list-ports"])
        if result["success"] and result["stdout"]:
            ports = []
            for port_proto in result["stdout"].split():
                if '/' in port_proto:
                    port, protocol = port_proto.split('/', 1)
                    ports.append({"port": port, "protocol": protocol})
            config["ports"] = ports
        
        # Get protocols
        result = await self.run_command(["firewall-cmd", "--zone", zone, "--list-protocols"])
        if result["success"] and result["stdout"]:
            config["protocols"] = result["stdout"].split()
        
        # Get masquerade
        result = await self.run_command(["firewall-cmd", "--zone", zone, "--query-masquerade"])
        config["masquerade"] = result["success"]
        
        # Get forward ports
        result = await self.run_command(["firewall-cmd", "--zone", zone, "--list-forward-ports"])
        if result["success"] and result["stdout"]:
            config["forward_ports"] = self._parse_forward_ports(result["stdout"])
        
        # Get source ports
        result = await self.run_command(["firewall-cmd", "--zone", zone, "--list-source-ports"])
        if result["success"] and result["stdout"]:
            source_ports = []
            for port_proto in result["stdout"].split():
                if '/' in port_proto:
                    port, protocol = port_proto.split('/', 1)
                    source_ports.append({"port": port, "protocol": protocol})
            config["source_ports"] = source_ports
        
        # Get ICMP blocks
        result = await self.run_command(["firewall-cmd", "--zone", zone, "--list-icmp-blocks"])
        if result["success"] and result["stdout"]:
            config["icmp_blocks"] = result["stdout"].split()
        
        # Get rich rules
        result = await self.run_command(["firewall-cmd", "--zone", zone, "--list-rich-rules"])
        if result["success"] and result["stdout"]:
            config["rich_rules"] = result["stdout"].split('\n')
        
        return config
    
    def _parse_forward_ports(self, output: str) -> List[Dict[str, str]]:
        """Parse forward ports output."""
        forward_ports = []
        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Parse format: port=PORT:proto=PROTOCOL[:toport=PORT][:toaddr=ADDRESS]
            parts = line.split(':')
            port_rule = {}
            
            for part in parts:
                if '=' in part:
                    key, value = part.split('=', 1)
                    if key == "port":
                        port_rule["port"] = value
                    elif key == "proto":
                        port_rule["protocol"] = value
                    elif key == "toport":
                        port_rule["to_port"] = value
                    elif key == "toaddr":
                        port_rule["to_addr"] = value
            
            if port_rule:
                forward_ports.append(port_rule)
        
        return forward_ports
    
    async def apply_configuration(self, config: FirewallConfiguration) -> bool:
        """Apply a complete firewall configuration."""
        try:
            self.logger.info("Applying firewall configuration",
                           agent_id=config.agent_id,
                           zones_count=len(config.zones))
            
            # Set default zone
            if config.default_zone:
                result = await self.run_command([
                    "firewall-cmd", "--set-default-zone", config.default_zone.value
                ])
                if not result["success"]:
                    return False
            
            # Apply zone configurations
            for zone_config in config.zones:
                if not await self.apply_zone_config(zone_config):
                    return False
            
            # Set panic mode
            if config.panic_mode:
                await self.run_command(["firewall-cmd", "--panic-on"])
            else:
                await self.run_command(["firewall-cmd", "--panic-off"])
            
            # Set lockdown mode
            if config.lockdown:
                await self.run_command(["firewall-cmd", "--lockdown-on"])
            else:
                await self.run_command(["firewall-cmd", "--lockdown-off"])
            
            # Make configuration permanent
            result = await self.run_command(["firewall-cmd", "--runtime-to-permanent"])
            
            return result["success"]
            
        except Exception as e:
            self.logger.error("Error applying configuration", error=str(e))
            return False
    
    async def apply_zone_config(self, zone_config: FirewallZoneConfig) -> bool:
        """Apply configuration for a specific zone."""
        zone = zone_config.zone.value
        
        try:
            # Set target if specified
            if zone_config.target:
                result = await self.run_command([
                    "firewall-cmd", "--zone", zone, "--set-target", zone_config.target.value
                ])
                if not result["success"]:
                    return False
            
            # Clear existing configuration
            await self._clear_zone_config(zone)
            
            # Add interfaces
            for interface in zone_config.interfaces:
                await self.run_command([
                    "firewall-cmd", "--zone", zone, "--add-interface", interface
                ])
            
            # Add sources
            for source in zone_config.sources:
                await self.run_command([
                    "firewall-cmd", "--zone", zone, "--add-source", source
                ])
            
            # Add services
            for service in zone_config.services:
                await self.run_command([
                    "firewall-cmd", "--zone", zone, "--add-service", service
                ])
            
            # Add ports
            for port_rule in zone_config.ports:
                await self.run_command([
                    "firewall-cmd", "--zone", zone, "--add-port",
                    f"{port_rule.port}/{port_rule.protocol}"
                ])
            
            # Add protocols
            for protocol in zone_config.protocols:
                await self.run_command([
                    "firewall-cmd", "--zone", zone, "--add-protocol", protocol
                ])
            
            # Set masquerade
            if zone_config.masquerade:
                await self.run_command([
                    "firewall-cmd", "--zone", zone, "--add-masquerade"
                ])
            
            # Add forward ports
            for forward_port in zone_config.forward_ports:
                cmd = [
                    "firewall-cmd", "--zone", zone, "--add-forward-port",
                    f"port={forward_port.port}:proto={forward_port.protocol}"
                ]
                if forward_port.to_port:
                    cmd[-1] += f":toport={forward_port.to_port}"
                if forward_port.to_addr:
                    cmd[-1] += f":toaddr={forward_port.to_addr}"
                
                await self.run_command(cmd)
            
            # Add source ports
            for source_port in zone_config.source_ports:
                await self.run_command([
                    "firewall-cmd", "--zone", zone, "--add-source-port",
                    f"{source_port.port}/{source_port.protocol}"
                ])
            
            # Add ICMP blocks
            for icmp_block in zone_config.icmp_blocks:
                await self.run_command([
                    "firewall-cmd", "--zone", zone, "--add-icmp-block", icmp_block
                ])
            
            # Add rich rules
            for rich_rule in zone_config.rich_rules:
                rule_str = self._build_rich_rule_string(rich_rule)
                if rule_str:
                    await self.run_command([
                        "firewall-cmd", "--zone", zone, "--add-rich-rule", rule_str
                    ])
            
            return True
            
        except Exception as e:
            self.logger.error("Error applying zone configuration",
                            zone=zone, error=str(e))
            return False
    
    async def _clear_zone_config(self, zone: str) -> None:
        """Clear existing configuration for a zone."""
        # Get current config and remove everything
        current_config = await self.get_zone_config(zone)
        
        # Remove services
        for service in current_config.get("services", []):
            await self.run_command([
                "firewall-cmd", "--zone", zone, "--remove-service", service
            ])
        
        # Remove ports
        for port in current_config.get("ports", []):
            await self.run_command([
                "firewall-cmd", "--zone", zone, "--remove-port",
                f"{port['port']}/{port['protocol']}"
            ])
        
        # Remove protocols
        for protocol in current_config.get("protocols", []):
            await self.run_command([
                "firewall-cmd", "--zone", zone, "--remove-protocol", protocol
            ])
        
        # Remove masquerade
        if current_config.get("masquerade"):
            await self.run_command([
                "firewall-cmd", "--zone", zone, "--remove-masquerade"
            ])
        
        # Remove rich rules
        for rule in current_config.get("rich_rules", []):
            if rule:
                await self.run_command([
                    "firewall-cmd", "--zone", zone, "--remove-rich-rule", rule
                ])
    
    def _build_rich_rule_string(self, rich_rule: RichRule) -> str:
        """Build a rich rule string from RichRule object."""
        parts = ["rule"]
        
        # Add family
        if rich_rule.family:
            parts.append(f"family={rich_rule.family.value}")
        
        # Add source
        if rich_rule.source:
            source_parts = []
            if rich_rule.source.address:
                source_parts.append(f"address={rich_rule.source.address}")
            if rich_rule.source.mac:
                source_parts.append(f"mac={rich_rule.source.mac}")
            if rich_rule.source.ipset:
                source_parts.append(f"ipset={rich_rule.source.ipset}")
            
            if source_parts:
                source_str = f"source {' '.join(source_parts)}"
                if rich_rule.source.invert:
                    source_str += " NOT"
                parts.append(source_str)
        
        # Add destination
        if rich_rule.destination:
            dest_str = f"destination address={rich_rule.destination.address}"
            if rich_rule.destination.invert:
                dest_str += " NOT"
            parts.append(dest_str)
        
        # Add service
        if rich_rule.service:
            parts.append(f"service name={rich_rule.service.service}")
        
        # Add port
        if rich_rule.port:
            parts.append(f"port port={rich_rule.port.port} protocol={rich_rule.port.protocol}")
        
        # Add protocol
        if rich_rule.protocol:
            parts.append(f"protocol value={rich_rule.protocol}")
        
        # Add masquerade
        if rich_rule.masquerade and rich_rule.masquerade.enabled:
            parts.append("masquerade")
        
        # Add forward port
        if rich_rule.forward_port:
            fp_str = f"forward-port port={rich_rule.forward_port.port} protocol={rich_rule.forward_port.protocol}"
            if rich_rule.forward_port.to_port:
                fp_str += f" to-port={rich_rule.forward_port.to_port}"
            if rich_rule.forward_port.to_addr:
                fp_str += f" to-addr={rich_rule.forward_port.to_addr}"
            parts.append(fp_str)
        
        # Add action
        if rich_rule.action:
            parts.append(rich_rule.action.value)
        
        # Add log
        if rich_rule.log:
            log_parts = ["log"]
            if "prefix" in rich_rule.log:
                log_parts.append(f"prefix={rich_rule.log['prefix']}")
            if "level" in rich_rule.log:
                log_parts.append(f"level={rich_rule.log['level']}")
            if "limit" in rich_rule.log:
                log_parts.append(f"limit value={rich_rule.log['limit']}")
            parts.append(" ".join(log_parts))
        
        # Add audit
        if rich_rule.audit:
            parts.append("audit")
        
        return " ".join(parts)
    
    async def add_rule(self, zone: str, rule_type: str, rule_data: Dict[str, Any]) -> bool:
        """Add a firewall rule."""
        try:
            if rule_type == "service":
                result = await self.run_command([
                    "firewall-cmd", "--zone", zone, "--add-service", rule_data["service"]
                ])
            elif rule_type == "port":
                result = await self.run_command([
                    "firewall-cmd", "--zone", zone, "--add-port",
                    f"{rule_data['port']}/{rule_data['protocol']}"
                ])
            elif rule_type == "rich_rule":
                rule_str = rule_data.get("rule_string")
                if not rule_str and "rich_rule" in rule_data:
                    rich_rule = RichRule(**rule_data["rich_rule"])
                    rule_str = self._build_rich_rule_string(rich_rule)
                
                if rule_str:
                    result = await self.run_command([
                        "firewall-cmd", "--zone", zone, "--add-rich-rule", rule_str
                    ])
                else:
                    return False
            else:
                self.logger.error("Unknown rule type", rule_type=rule_type)
                return False
            
            return result["success"]
            
        except Exception as e:
            self.logger.error("Error adding rule",
                            zone=zone, rule_type=rule_type, error=str(e))
            return False
    
    async def remove_rule(self, zone: str, rule_type: str, rule_data: Dict[str, Any]) -> bool:
        """Remove a firewall rule."""
        try:
            if rule_type == "service":
                result = await self.run_command([
                    "firewall-cmd", "--zone", zone, "--remove-service", rule_data["service"]
                ])
            elif rule_type == "port":
                result = await self.run_command([
                    "firewall-cmd", "--zone", zone, "--remove-port",
                    f"{rule_data['port']}/{rule_data['protocol']}"
                ])
            elif rule_type == "rich_rule":
                rule_str = rule_data.get("rule_string")
                if not rule_str and "rich_rule" in rule_data:
                    rich_rule = RichRule(**rule_data["rich_rule"])
                    rule_str = self._build_rich_rule_string(rich_rule)
                
                if rule_str:
                    result = await self.run_command([
                        "firewall-cmd", "--zone", zone, "--remove-rich-rule", rule_str
                    ])
                else:
                    return False
            else:
                self.logger.error("Unknown rule type", rule_type=rule_type)
                return False
            
            return result["success"]
            
        except Exception as e:
            self.logger.error("Error removing rule",
                            zone=zone, rule_type=rule_type, error=str(e))
            return False
    
    async def reload(self) -> bool:
        """Reload firewalld configuration."""
        result = await self.run_command(["firewall-cmd", "--reload"])
        return result["success"]