#!/usr/bin/env python3
"""
KillKrill XDP Filter Manager
Manages XDP packet filtering with CIDR support and metrics collection
"""

import ctypes
import json
import logging
import os
import socket
import struct
import subprocess
import sys
import time
from ctypes import c_uint32, c_uint16, c_uint8, c_uint64, Structure
from ipaddress import IPv4Network, IPv4Address
from typing import List, Dict, Optional, Tuple

# Try to import BPF libraries
try:
    from bcc import BPF
    HAS_BCC = True
except ImportError:
    HAS_BCC = False
    logging.warning("BCC library not available, XDP filtering disabled")

try:
    import pyroute2
    HAS_PYROUTE2 = True
except ImportError:
    HAS_PYROUTE2 = False
    logging.warning("Pyroute2 library not available, limited XDP functionality")


class CIDRRule(Structure):
    """CIDR rule structure matching the C struct"""
    _fields_ = [
        ("network", c_uint32),
        ("mask", c_uint32),
        ("port", c_uint16),
        ("enabled", c_uint8),
        ("reserved", c_uint8),
    ]


class XDPStats(Structure):
    """XDP statistics structure matching the C struct"""
    _fields_ = [
        ("packets_total", c_uint64),
        ("packets_allowed", c_uint64),
        ("packets_blocked", c_uint64),
        ("bytes_total", c_uint64),
        ("bytes_allowed", c_uint64),
        ("bytes_blocked", c_uint64),
        ("tcp_packets", c_uint64),
        ("udp_packets", c_uint64),
        ("syslog_packets", c_uint64),
        ("api_packets", c_uint64),
    ]


class XDPFilterManager:
    """Manages XDP packet filtering with CIDR support"""

    def __init__(self, interface: str = None, program_path: str = None):
        self.interface = interface or self._detect_interface()
        self.program_path = program_path or "/app/xdp_filter.o"
        self.bpf = None
        self.logger = logging.getLogger(__name__)
        self.enabled = HAS_BCC and HAS_PYROUTE2

        if not self.enabled:
            self.logger.warning("XDP filtering disabled due to missing dependencies")

    def _detect_interface(self) -> str:
        """Auto-detect the primary network interface"""
        try:
            # Get the interface used for the default route
            result = subprocess.run(
                ["ip", "route", "show", "default"],
                capture_output=True, text=True, check=True
            )

            for line in result.stdout.splitlines():
                if "dev" in line:
                    parts = line.split()
                    if "dev" in parts:
                        dev_idx = parts.index("dev")
                        if dev_idx + 1 < len(parts):
                            return parts[dev_idx + 1]

            # Fallback to eth0
            return "eth0"
        except Exception as e:
            self.logger.warning(f"Could not detect interface: {e}, using eth0")
            return "eth0"

    def _compile_xdp_program(self) -> bool:
        """Compile the XDP program using clang"""
        try:
            cmd = [
                "clang",
                "-O2",
                "-target", "bpf",
                "-c", "/app/xdp_filter.c",
                "-o", self.program_path,
                "-I/usr/include/bpf"
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                self.logger.error(f"XDP compilation failed: {result.stderr}")
                return False

            self.logger.info("XDP program compiled successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to compile XDP program: {e}")
            return False

    def load_program(self) -> bool:
        """Load and attach the XDP program"""
        if not self.enabled:
            return False

        try:
            # Compile the program if it doesn't exist
            if not os.path.exists(self.program_path):
                if not self._compile_xdp_program():
                    return False

            # Load the XDP program
            with open("/app/xdp_filter.c", "r") as f:
                program_text = f.read()

            self.bpf = BPF(text=program_text)

            # Get the function
            fn = self.bpf.load_func("xdp_filter_func", BPF.XDP)

            # Attach to interface
            self.bpf.attach_xdp(self.interface, fn, 0)

            self.logger.info(f"XDP program loaded and attached to {self.interface}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to load XDP program: {e}")
            return False

    def unload_program(self) -> bool:
        """Unload and detach the XDP program"""
        if not self.enabled or not self.bpf:
            return True

        try:
            self.bpf.remove_xdp(self.interface, 0)
            self.bpf = None
            self.logger.info(f"XDP program unloaded from {self.interface}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to unload XDP program: {e}")
            return False

    def _ip_to_uint32(self, ip_str: str) -> int:
        """Convert IP address string to uint32 in network byte order"""
        return struct.unpack("!I", socket.inet_aton(ip_str))[0]

    def _cidr_to_mask(self, prefix_len: int) -> int:
        """Convert CIDR prefix length to subnet mask"""
        return (0xFFFFFFFF << (32 - prefix_len)) & 0xFFFFFFFF

    def update_cidr_rules(self, cidr_rules: List[Dict]) -> bool:
        """Update CIDR rules in the XDP program"""
        if not self.enabled or not self.bpf:
            self.logger.warning("XDP not available, skipping CIDR rule update")
            return False

        try:
            cidr_map = self.bpf["cidr_rules"]

            # Clear existing rules
            for i in range(1024):  # MAX_CIDR_RULES
                rule = CIDRRule()
                rule.enabled = 0
                cidr_map[ctypes.c_uint32(i)] = rule

            # Add new rules
            for idx, rule_data in enumerate(cidr_rules[:1024]):
                if idx >= 1024:
                    break

                try:
                    network = IPv4Network(rule_data["cidr"], strict=False)
                    port = rule_data.get("port", 0)
                    enabled = rule_data.get("enabled", True)

                    rule = CIDRRule()
                    rule.network = self._ip_to_uint32(str(network.network_address))
                    rule.mask = self._cidr_to_mask(network.prefixlen)
                    rule.port = port
                    rule.enabled = 1 if enabled else 0

                    cidr_map[ctypes.c_uint32(idx)] = rule

                    self.logger.debug(f"Added CIDR rule {idx}: {rule_data['cidr']} port={port}")

                except Exception as e:
                    self.logger.error(f"Invalid CIDR rule {rule_data}: {e}")
                    continue

            self.logger.info(f"Updated {len(cidr_rules)} CIDR rules")
            return True

        except Exception as e:
            self.logger.error(f"Failed to update CIDR rules: {e}")
            return False

    def update_allowed_ports(self, ports: List[int]) -> bool:
        """Update allowed ports in the XDP program"""
        if not self.enabled or not self.bpf:
            self.logger.warning("XDP not available, skipping port update")
            return False

        try:
            ports_map = self.bpf["allowed_ports"]

            # Clear existing ports
            for i in range(64):  # MAX_PORT_RULES
                ports_map[ctypes.c_uint32(i)] = ctypes.c_uint16(0)

            # Add new ports
            for idx, port in enumerate(ports[:64]):
                if idx >= 64:
                    break
                ports_map[ctypes.c_uint32(idx)] = ctypes.c_uint16(port)

            self.logger.info(f"Updated {len(ports)} allowed ports")
            return True

        except Exception as e:
            self.logger.error(f"Failed to update allowed ports: {e}")
            return False

    def get_statistics(self) -> Dict:
        """Get XDP filtering statistics"""
        if not self.enabled or not self.bpf:
            return {
                "enabled": False,
                "packets_total": 0,
                "packets_allowed": 0,
                "packets_blocked": 0,
                "bytes_total": 0,
                "bytes_allowed": 0,
                "bytes_blocked": 0,
                "tcp_packets": 0,
                "udp_packets": 0,
                "syslog_packets": 0,
                "api_packets": 0,
                "block_rate": 0.0,
                "throughput_mbps": 0.0
            }

        try:
            stats_map = self.bpf["xdp_statistics"]
            key = ctypes.c_uint32(0)

            # Get per-CPU stats and sum them
            stats_array = stats_map.getvalue(key)
            total_stats = XDPStats()

            for cpu_stats in stats_array:
                stats = ctypes.cast(cpu_stats, ctypes.POINTER(XDPStats)).contents
                total_stats.packets_total += stats.packets_total
                total_stats.packets_allowed += stats.packets_allowed
                total_stats.packets_blocked += stats.packets_blocked
                total_stats.bytes_total += stats.bytes_total
                total_stats.bytes_allowed += stats.bytes_allowed
                total_stats.bytes_blocked += stats.bytes_blocked
                total_stats.tcp_packets += stats.tcp_packets
                total_stats.udp_packets += stats.udp_packets
                total_stats.syslog_packets += stats.syslog_packets
                total_stats.api_packets += stats.api_packets

            # Calculate rates
            block_rate = 0.0
            if total_stats.packets_total > 0:
                block_rate = (total_stats.packets_blocked / total_stats.packets_total) * 100

            # Estimate throughput (bytes/sec converted to Mbps)
            throughput_mbps = 0.0
            if hasattr(self, '_last_bytes') and hasattr(self, '_last_time'):
                time_diff = time.time() - self._last_time
                if time_diff > 0:
                    bytes_diff = total_stats.bytes_total - self._last_bytes
                    throughput_mbps = (bytes_diff * 8) / (time_diff * 1_000_000)

            self._last_bytes = total_stats.bytes_total
            self._last_time = time.time()

            return {
                "enabled": True,
                "interface": self.interface,
                "packets_total": total_stats.packets_total,
                "packets_allowed": total_stats.packets_allowed,
                "packets_blocked": total_stats.packets_blocked,
                "bytes_total": total_stats.bytes_total,
                "bytes_allowed": total_stats.bytes_allowed,
                "bytes_blocked": total_stats.bytes_blocked,
                "tcp_packets": total_stats.tcp_packets,
                "udp_packets": total_stats.udp_packets,
                "syslog_packets": total_stats.syslog_packets,
                "api_packets": total_stats.api_packets,
                "block_rate": round(block_rate, 2),
                "throughput_mbps": round(throughput_mbps, 2)
            }

        except Exception as e:
            self.logger.error(f"Failed to get XDP statistics: {e}")
            return {"enabled": False, "error": str(e)}

    def reload_config(self, config: Dict) -> bool:
        """Reload XDP configuration from database/config"""
        if not self.enabled:
            return False

        try:
            # Update CIDR rules
            cidr_rules = config.get("cidr_rules", [])
            self.update_cidr_rules(cidr_rules)

            # Update allowed ports
            allowed_ports = config.get("allowed_ports", [])
            self.update_allowed_ports(allowed_ports)

            self.logger.info("XDP configuration reloaded successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to reload XDP configuration: {e}")
            return False

    def is_available(self) -> bool:
        """Check if XDP filtering is available"""
        return self.enabled

    def get_status(self) -> Dict:
        """Get XDP filter status"""
        return {
            "available": self.enabled,
            "loaded": self.bpf is not None,
            "interface": self.interface,
            "dependencies": {
                "bcc": HAS_BCC,
                "pyroute2": HAS_PYROUTE2
            }
        }


def main():
    """Command-line interface for XDP manager"""
    import argparse

    parser = argparse.ArgumentParser(description="KillKrill XDP Filter Manager")
    parser.add_argument("--interface", "-i", help="Network interface")
    parser.add_argument("--load", action="store_true", help="Load XDP program")
    parser.add_argument("--unload", action="store_true", help="Unload XDP program")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--config", help="Configuration file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    manager = XDPFilterManager(interface=args.interface)

    if args.status:
        status = manager.get_status()
        print(json.dumps(status, indent=2))
        return

    if args.load:
        if manager.load_program():
            print("XDP program loaded successfully")
        else:
            print("Failed to load XDP program")
            sys.exit(1)

    if args.unload:
        if manager.unload_program():
            print("XDP program unloaded successfully")
        else:
            print("Failed to unload XDP program")
            sys.exit(1)

    if args.stats:
        stats = manager.get_statistics()
        print(json.dumps(stats, indent=2))

    if args.config:
        with open(args.config, 'r') as f:
            config = json.load(f)

        if manager.reload_config(config):
            print("Configuration reloaded successfully")
        else:
            print("Failed to reload configuration")
            sys.exit(1)


if __name__ == "__main__":
    main()