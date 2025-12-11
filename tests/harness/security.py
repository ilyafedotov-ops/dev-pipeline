#!/usr/bin/env python3
"""
Security and reliability hardening for CLI workflow harness.

This script implements task 18.2 - Security and reliability hardening.
It implements input validation and sanitization, secure credential and secret
management, audit logging and compliance features, and security scanning
and vulnerability assessment.
"""

import sys
import json
import time
import logging
import hashlib
import secrets
import re
import os
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set, Union
from dataclasses import dataclass, asdict
from enum import Enum
import tempfile
import shutil

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class SecurityLevel(Enum):
    """Security levels for different operations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditEventType(Enum):
    """Types of audit events."""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_ACCESS = "data_access"
    CONFIGURATION_CHANGE = "configuration_change"
    SECURITY_VIOLATION = "security_violation"
    SYSTEM_EVENT = "system_event"
    ERROR = "error"


@dataclass
class SecurityViolation:
    """Security violation record."""
    violation_id: str
    timestamp: datetime
    violation_type: str
    severity: SecurityLevel
    description: str
    source_ip: Optional[str]
    user_context: Optional[str]
    affected_resource: Optional[str]
    mitigation_applied: bool
    details: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        result['severity'] = self.severity.value
        return result


@dataclass
class AuditEvent:
    """Audit event record."""
    event_id: str
    timestamp: datetime
    event_type: AuditEventType
    severity: SecurityLevel
    user_context: Optional[str]
    resource: Optional[str]
    action: str
    result: str  # "success", "failure", "error"
    details: Dict[str, Any]
    source_info: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        result['event_type'] = self.event_type.value
        result['severity'] = self.severity.value
        return result


@dataclass
class SecurityAssessmentResult:
    """Result of security assessment."""
    assessment_id: str
    timestamp: datetime
    overall_security_score: float  # 0-100
    vulnerabilities_found: int
    critical_issues: int
    high_issues: int
    medium_issues: int
    low_issues: int
    compliance_score: float  # 0-100
    audit_events_analyzed: int
    security_violations: int
    recommendations: List[str]
    detailed_findings: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result


class InputValidator:
    """Comprehensive input validation and sanitization."""
    
    # Dangerous patterns that should be blocked
    DANGEROUS_PATTERNS = [
        r'[;&|`$(){}[\]<>]',  # Shell metacharacters
        r'\.\./',  # Path traversal
        r'<script[^>]*>',  # Script injection
        r'javascript:',  # JavaScript protocol
        r'data:',  # Data protocol
        r'vbscript:',  # VBScript protocol
        r'on\w+\s*=',  # Event handlers
        r'eval\s*\(',  # Eval function
        r'exec\s*\(',  # Exec function
        r'system\s*\(',  # System function
        r'__import__',  # Python import
        r'subprocess',  # Subprocess module
        r'os\.system',  # OS system calls
    ]
    
    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"'.*?'",  # Single quotes
        r'".*?"',  # Double quotes
        r'union\s+select',  # Union select
        r'drop\s+table',  # Drop table
        r'delete\s+from',  # Delete from
        r'insert\s+into',  # Insert into
        r'update\s+.*?set',  # Update set
        r'--',  # SQL comments
        r'/\*.*?\*/',  # SQL block comments
    ]
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.violation_count = 0
    
    def validate_string_input(self, input_value: str, 
                            max_length: int = 1000,
                            allow_special_chars: bool = False,
                            context: str = "unknown") -> Tuple[bool, str, Optional[str]]:
        """
        Validate and sanitize string input.
        
        Returns:
            Tuple of (is_valid, sanitized_value, error_message)
        """
        if not isinstance(input_value, str):
            return False, "", "Input must be a string"
        
        # Check length
        if len(input_value) > max_length:
            return False, "", f"Input exceeds maximum length of {max_length} characters"
        
        # Check for dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, input_value, re.IGNORECASE):
                self.violation_count += 1
                self.logger.warning(f"Dangerous pattern detected in {context}: {pattern}")
                return False, "", f"Input contains potentially dangerous content"
        
        # Check for SQL injection patterns
        for pattern in self.SQL_INJECTION_PATTERNS:
            if re.search(pattern, input_value, re.IGNORECASE):
                self.violation_count += 1
                self.logger.warning(f"SQL injection pattern detected in {context}: {pattern}")
                return False, "", f"Input contains potentially malicious SQL content"
        
        # Sanitize the input
        sanitized = self._sanitize_string(input_value, allow_special_chars)
        
        return True, sanitized, None
    
    def validate_path_input(self, path_value: str, 
                          base_path: Optional[Path] = None,
                          must_exist: bool = False) -> Tuple[bool, Path, Optional[str]]:
        """
        Validate and sanitize path input.
        
        Returns:
            Tuple of (is_valid, sanitized_path, error_message)
        """
        if not isinstance(path_value, str):
            return False, Path(), "Path must be a string"
        
        # Check for path traversal attempts
        if '..' in path_value or path_value.startswith('/'):
            self.violation_count += 1
            self.logger.warning(f"Path traversal attempt detected: {path_value}")
            return False, Path(), "Path contains invalid traversal sequences"
        
        try:
            path = Path(path_value)
            
            # Resolve against base path if provided
            if base_path:
                path = base_path / path
                path = path.resolve()
                
                # Ensure the resolved path is still within the base path
                if not str(path).startswith(str(base_path.resolve())):
                    self.violation_count += 1
                    self.logger.warning(f"Path escape attempt detected: {path_value}")
                    return False, Path(), "Path attempts to escape base directory"
            
            # Check if path must exist
            if must_exist and not path.exists():
                return False, Path(), f"Path does not exist: {path}"
            
            return True, path, None
            
        except Exception as e:
            return False, Path(), f"Invalid path format: {e}"
    
    def validate_json_input(self, json_value: str, 
                          max_size: int = 10000) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """
        Validate and parse JSON input.
        
        Returns:
            Tuple of (is_valid, parsed_json, error_message)
        """
        if not isinstance(json_value, str):
            return False, {}, "JSON input must be a string"
        
        # Check size
        if len(json_value) > max_size:
            return False, {}, f"JSON input exceeds maximum size of {max_size} bytes"
        
        # Check for dangerous content in JSON
        is_valid, _, error = self.validate_string_input(json_value, max_size, False, "json")
        if not is_valid:
            return False, {}, error
        
        try:
            parsed = json.loads(json_value)
            
            # Recursively validate JSON content
            if not self._validate_json_content(parsed):
                return False, {}, "JSON contains potentially dangerous content"
            
            return True, parsed, None
            
        except json.JSONDecodeError as e:
            return False, {}, f"Invalid JSON format: {e}"
    
    def validate_command_input(self, command: str, 
                             allowed_commands: Optional[Set[str]] = None) -> Tuple[bool, str, Optional[str]]:
        """
        Validate command input for execution.
        
        Returns:
            Tuple of (is_valid, sanitized_command, error_message)
        """
        if not isinstance(command, str):
            return False, "", "Command must be a string"
        
        # Check if command is in allowed list
        if allowed_commands:
            command_name = command.split()[0] if command.split() else ""
            if command_name not in allowed_commands:
                self.violation_count += 1
                self.logger.warning(f"Unauthorized command attempted: {command_name}")
                return False, "", f"Command not in allowed list: {command_name}"
        
        # Check for command injection patterns
        dangerous_chars = [';', '&', '|', '`', '$', '(', ')', '{', '}', '<', '>']
        for char in dangerous_chars:
            if char in command:
                self.violation_count += 1
                self.logger.warning(f"Command injection attempt detected: {command}")
                return False, "", "Command contains potentially dangerous characters"
        
        return True, command.strip(), None
    
    def _sanitize_string(self, value: str, allow_special_chars: bool) -> str:
        """Sanitize string input by removing or escaping dangerous content."""
        # Remove null bytes
        value = value.replace('\x00', '')
        
        # Remove or escape special characters if not allowed
        if not allow_special_chars:
            # Keep only alphanumeric, spaces, and basic punctuation
            value = re.sub(r'[^\w\s\-_.,!?@#]', '', value)
        
        # Normalize whitespace
        value = ' '.join(value.split())
        
        return value
    
    def _validate_json_content(self, obj: Any, depth: int = 0) -> bool:
        """Recursively validate JSON content for dangerous patterns."""
        if depth > 10:  # Prevent deep recursion
            return False
        
        if isinstance(obj, dict):
            for key, value in obj.items():
                if not isinstance(key, str):
                    return False
                
                # Validate key
                is_valid, _, _ = self.validate_string_input(key, 100, False, "json_key")
                if not is_valid:
                    return False
                
                # Recursively validate value
                if not self._validate_json_content(value, depth + 1):
                    return False
        
        elif isinstance(obj, list):
            for item in obj:
                if not self._validate_json_content(item, depth + 1):
                    return False
        
        elif isinstance(obj, str):
            # Validate string content
            is_valid, _, _ = self.validate_string_input(obj, 1000, False, "json_value")
            if not is_valid:
                return False
        
        return True


class SecretManager:
    """Secure credential and secret management."""
    
    def __init__(self, secrets_dir: Path = None):
        self.secrets_dir = secrets_dir or Path.home() / ".tasksgodzilla" / "secrets"
        self.secrets_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.logger = logging.getLogger(__name__)
        self._secrets_cache = {}
        self._key_derivation_salt = self._get_or_create_salt()
    
    def store_secret(self, key: str, value: str, 
                    description: str = "", 
                    expires_at: Optional[datetime] = None) -> bool:
        """
        Store a secret securely.
        
        Args:
            key: Secret identifier
            value: Secret value
            description: Optional description
            expires_at: Optional expiration time
            
        Returns:
            True if stored successfully
        """
        try:
            # Validate inputs
            validator = InputValidator()
            is_valid, sanitized_key, error = validator.validate_string_input(
                key, max_length=100, allow_special_chars=False, context="secret_key"
            )
            if not is_valid:
                self.logger.error(f"Invalid secret key: {error}")
                return False
            
            # Create secret record
            secret_record = {
                "key": sanitized_key,
                "value": self._encrypt_value(value),
                "description": description,
                "created_at": datetime.now().isoformat(),
                "expires_at": expires_at.isoformat() if expires_at else None,
                "access_count": 0,
                "last_accessed": None,
            }
            
            # Store to file
            secret_file = self.secrets_dir / f"{sanitized_key}.json"
            with open(secret_file, 'w', mode=0o600) as f:
                json.dump(secret_record, f, indent=2)
            
            # Set restrictive permissions
            secret_file.chmod(0o600)
            
            self.logger.info(f"Secret stored: {sanitized_key}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to store secret {key}: {e}")
            return False
    
    def retrieve_secret(self, key: str) -> Optional[str]:
        """
        Retrieve a secret value.
        
        Args:
            key: Secret identifier
            
        Returns:
            Secret value if found and valid, None otherwise
        """
        try:
            # Check cache first
            if key in self._secrets_cache:
                cached_secret, cached_time = self._secrets_cache[key]
                if time.time() - cached_time < 300:  # 5 minute cache
                    return cached_secret
            
            secret_file = self.secrets_dir / f"{key}.json"
            if not secret_file.exists():
                return None
            
            with open(secret_file, 'r') as f:
                secret_record = json.load(f)
            
            # Check expiration
            if secret_record.get("expires_at"):
                expires_at = datetime.fromisoformat(secret_record["expires_at"])
                if datetime.now() > expires_at:
                    self.logger.warning(f"Secret expired: {key}")
                    self._delete_secret_file(secret_file)
                    return None
            
            # Decrypt value
            decrypted_value = self._decrypt_value(secret_record["value"])
            
            # Update access tracking
            secret_record["access_count"] += 1
            secret_record["last_accessed"] = datetime.now().isoformat()
            
            with open(secret_file, 'w') as f:
                json.dump(secret_record, f, indent=2)
            
            # Cache the result
            self._secrets_cache[key] = (decrypted_value, time.time())
            
            self.logger.debug(f"Secret retrieved: {key}")
            return decrypted_value
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve secret {key}: {e}")
            return None
    
    def delete_secret(self, key: str) -> bool:
        """
        Delete a secret.
        
        Args:
            key: Secret identifier
            
        Returns:
            True if deleted successfully
        """
        try:
            secret_file = self.secrets_dir / f"{key}.json"
            if secret_file.exists():
                self._delete_secret_file(secret_file)
                
                # Remove from cache
                if key in self._secrets_cache:
                    del self._secrets_cache[key]
                
                self.logger.info(f"Secret deleted: {key}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to delete secret {key}: {e}")
            return False
    
    def list_secrets(self) -> List[Dict[str, Any]]:
        """
        List all stored secrets (metadata only).
        
        Returns:
            List of secret metadata
        """
        secrets = []
        
        try:
            for secret_file in self.secrets_dir.glob("*.json"):
                try:
                    with open(secret_file, 'r') as f:
                        secret_record = json.load(f)
                    
                    # Return metadata only (no secret value)
                    metadata = {
                        "key": secret_record.get("key"),
                        "description": secret_record.get("description", ""),
                        "created_at": secret_record.get("created_at"),
                        "expires_at": secret_record.get("expires_at"),
                        "access_count": secret_record.get("access_count", 0),
                        "last_accessed": secret_record.get("last_accessed"),
                    }
                    
                    secrets.append(metadata)
                    
                except Exception as e:
                    self.logger.error(f"Failed to read secret file {secret_file}: {e}")
            
        except Exception as e:
            self.logger.error(f"Failed to list secrets: {e}")
        
        return secrets
    
    def cleanup_expired_secrets(self) -> int:
        """
        Clean up expired secrets.
        
        Returns:
            Number of secrets cleaned up
        """
        cleaned_count = 0
        
        try:
            for secret_file in self.secrets_dir.glob("*.json"):
                try:
                    with open(secret_file, 'r') as f:
                        secret_record = json.load(f)
                    
                    if secret_record.get("expires_at"):
                        expires_at = datetime.fromisoformat(secret_record["expires_at"])
                        if datetime.now() > expires_at:
                            self._delete_secret_file(secret_file)
                            cleaned_count += 1
                            
                except Exception as e:
                    self.logger.error(f"Failed to check expiration for {secret_file}: {e}")
            
            if cleaned_count > 0:
                self.logger.info(f"Cleaned up {cleaned_count} expired secrets")
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup expired secrets: {e}")
        
        return cleaned_count
    
    def _get_or_create_salt(self) -> bytes:
        """Get or create salt for key derivation."""
        salt_file = self.secrets_dir / ".salt"
        
        if salt_file.exists():
            return salt_file.read_bytes()
        else:
            salt = secrets.token_bytes(32)
            salt_file.write_bytes(salt)
            salt_file.chmod(0o600)
            return salt
    
    def _encrypt_value(self, value: str) -> str:
        """Encrypt a secret value (simplified implementation)."""
        # In a real implementation, use proper encryption like Fernet
        # This is a simplified version for demonstration
        import base64
        encoded = base64.b64encode(value.encode()).decode()
        return encoded
    
    def _decrypt_value(self, encrypted_value: str) -> str:
        """Decrypt a secret value (simplified implementation)."""
        # In a real implementation, use proper decryption like Fernet
        # This is a simplified version for demonstration
        import base64
        decoded = base64.b64decode(encrypted_value.encode()).decode()
        return decoded
    
    def _delete_secret_file(self, secret_file: Path) -> None:
        """Securely delete a secret file."""
        try:
            # Overwrite file content before deletion
            file_size = secret_file.stat().st_size
            with open(secret_file, 'r+b') as f:
                f.write(secrets.token_bytes(file_size))
                f.flush()
                os.fsync(f.fileno())
            
            # Delete the file
            secret_file.unlink()
            
        except Exception as e:
            self.logger.error(f"Failed to securely delete {secret_file}: {e}")
            # Fallback to regular deletion
            try:
                secret_file.unlink()
            except Exception:
                pass

class AuditLogger:
    """Comprehensive audit logging and compliance features."""
    
    def __init__(self, audit_dir: Path = None):
        self.audit_dir = audit_dir or Path("./audit-logs")
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        self.session_id = secrets.token_hex(16)
        self.audit_events = []
        
        # Configure audit file logging
        audit_file = self.audit_dir / f"audit_{datetime.now().strftime('%Y%m%d')}.log"
        self.audit_handler = logging.FileHandler(audit_file)
        self.audit_handler.setLevel(logging.INFO)
        
        # Create audit-specific formatter
        audit_formatter = logging.Formatter(
            '%(asctime)s - AUDIT - %(levelname)s - %(message)s'
        )
        self.audit_handler.setFormatter(audit_formatter)
        
        # Create audit logger
        self.audit_logger = logging.getLogger('audit')
        self.audit_logger.addHandler(self.audit_handler)
        self.audit_logger.setLevel(logging.INFO)
        
        # Log session start
        self.log_audit_event(
            event_type=AuditEventType.SYSTEM_EVENT,
            action="session_start",
            result="success",
            details={"session_id": self.session_id}
        )
    
    def log_audit_event(self, 
                       event_type: AuditEventType,
                       action: str,
                       result: str,
                       user_context: Optional[str] = None,
                       resource: Optional[str] = None,
                       severity: SecurityLevel = SecurityLevel.MEDIUM,
                       details: Optional[Dict[str, Any]] = None,
                       source_info: Optional[Dict[str, Any]] = None) -> str:
        """
        Log an audit event.
        
        Returns:
            Event ID
        """
        event_id = secrets.token_hex(16)
        
        audit_event = AuditEvent(
            event_id=event_id,
            timestamp=datetime.now(),
            event_type=event_type,
            severity=severity,
            user_context=user_context,
            resource=resource,
            action=action,
            result=result,
            details=details or {},
            source_info=source_info or {}
        )
        
        # Add to in-memory collection
        self.audit_events.append(audit_event)
        
        # Log to audit file
        audit_message = json.dumps(audit_event.to_dict())
        self.audit_logger.info(audit_message)
        
        # Log to console for high severity events
        if severity in [SecurityLevel.HIGH, SecurityLevel.CRITICAL]:
            self.logger.warning(f"High severity audit event: {action} - {result}")
        
        return event_id
    
    def log_security_violation(self,
                             violation_type: str,
                             description: str,
                             severity: SecurityLevel = SecurityLevel.HIGH,
                             source_ip: Optional[str] = None,
                             user_context: Optional[str] = None,
                             affected_resource: Optional[str] = None,
                             mitigation_applied: bool = False,
                             details: Optional[Dict[str, Any]] = None) -> str:
        """
        Log a security violation.
        
        Returns:
            Violation ID
        """
        violation_id = secrets.token_hex(16)
        
        violation = SecurityViolation(
            violation_id=violation_id,
            timestamp=datetime.now(),
            violation_type=violation_type,
            severity=severity,
            description=description,
            source_ip=source_ip,
            user_context=user_context,
            affected_resource=affected_resource,
            mitigation_applied=mitigation_applied,
            details=details or {}
        )
        
        # Log as audit event
        self.log_audit_event(
            event_type=AuditEventType.SECURITY_VIOLATION,
            action=f"security_violation_{violation_type}",
            result="violation_detected",
            user_context=user_context,
            resource=affected_resource,
            severity=severity,
            details=violation.to_dict()
        )
        
        # Save violation to separate file for analysis
        violation_file = self.audit_dir / f"violations_{datetime.now().strftime('%Y%m%d')}.json"
        
        violations = []
        if violation_file.exists():
            try:
                with open(violation_file, 'r') as f:
                    violations = json.load(f)
            except Exception:
                violations = []
        
        violations.append(violation.to_dict())
        
        with open(violation_file, 'w') as f:
            json.dump(violations, f, indent=2)
        
        self.logger.error(f"Security violation logged: {violation_type} - {description}")
        
        return violation_id
    
    def generate_audit_report(self, 
                            start_date: Optional[datetime] = None,
                            end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Generate comprehensive audit report.
        
        Args:
            start_date: Start date for report (default: 24 hours ago)
            end_date: End date for report (default: now)
            
        Returns:
            Audit report data
        """
        if not start_date:
            start_date = datetime.now() - timedelta(days=1)
        if not end_date:
            end_date = datetime.now()
        
        # Filter events by date range
        filtered_events = [
            event for event in self.audit_events
            if start_date <= event.timestamp <= end_date
        ]
        
        # Analyze events
        event_counts = {}
        severity_counts = {}
        result_counts = {}
        
        for event in filtered_events:
            # Count by event type
            event_type = event.event_type.value
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
            
            # Count by severity
            severity = event.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            # Count by result
            result = event.result
            result_counts[result] = result_counts.get(result, 0) + 1
        
        # Load security violations for the period
        violations = self._load_violations_for_period(start_date, end_date)
        
        report = {
            "report_id": secrets.token_hex(16),
            "generated_at": datetime.now().isoformat(),
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "summary": {
                "total_events": len(filtered_events),
                "total_violations": len(violations),
                "event_counts": event_counts,
                "severity_counts": severity_counts,
                "result_counts": result_counts
            },
            "violations": violations,
            "top_events": [event.to_dict() for event in filtered_events[:10]],
            "compliance_status": self._assess_compliance(filtered_events, violations)
        }
        
        return report
    
    def export_audit_logs(self, 
                         output_file: Path,
                         format: str = "json",
                         start_date: Optional[datetime] = None,
                         end_date: Optional[datetime] = None) -> bool:
        """
        Export audit logs to file.
        
        Args:
            output_file: Output file path
            format: Export format ("json", "csv")
            start_date: Start date for export
            end_date: End date for export
            
        Returns:
            True if exported successfully
        """
        try:
            if not start_date:
                start_date = datetime.now() - timedelta(days=30)
            if not end_date:
                end_date = datetime.now()
            
            # Filter events by date range
            filtered_events = [
                event for event in self.audit_events
                if start_date <= event.timestamp <= end_date
            ]
            
            if format.lower() == "json":
                export_data = {
                    "export_info": {
                        "exported_at": datetime.now().isoformat(),
                        "period": {
                            "start_date": start_date.isoformat(),
                            "end_date": end_date.isoformat()
                        },
                        "total_events": len(filtered_events)
                    },
                    "events": [event.to_dict() for event in filtered_events]
                }
                
                with open(output_file, 'w') as f:
                    json.dump(export_data, f, indent=2)
            
            elif format.lower() == "csv":
                import csv
                
                with open(output_file, 'w', newline='') as f:
                    writer = csv.writer(f)
                    
                    # Write header
                    writer.writerow([
                        'event_id', 'timestamp', 'event_type', 'severity',
                        'user_context', 'resource', 'action', 'result'
                    ])
                    
                    # Write events
                    for event in filtered_events:
                        writer.writerow([
                            event.event_id,
                            event.timestamp.isoformat(),
                            event.event_type.value,
                            event.severity.value,
                            event.user_context or '',
                            event.resource or '',
                            event.action,
                            event.result
                        ])
            
            self.logger.info(f"Audit logs exported to {output_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to export audit logs: {e}")
            return False
    
    def _load_violations_for_period(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Load security violations for a specific period."""
        violations = []
        
        try:
            # Check violation files for the period
            current_date = start_date.date()
            end_date_only = end_date.date()
            
            while current_date <= end_date_only:
                violation_file = self.audit_dir / f"violations_{current_date.strftime('%Y%m%d')}.json"
                
                if violation_file.exists():
                    try:
                        with open(violation_file, 'r') as f:
                            daily_violations = json.load(f)
                        
                        # Filter by time range
                        for violation in daily_violations:
                            violation_time = datetime.fromisoformat(violation['timestamp'])
                            if start_date <= violation_time <= end_date:
                                violations.append(violation)
                                
                    except Exception as e:
                        self.logger.error(f"Failed to load violations from {violation_file}: {e}")
                
                current_date += timedelta(days=1)
                
        except Exception as e:
            self.logger.error(f"Failed to load violations for period: {e}")
        
        return violations
    
    def _assess_compliance(self, events: List[AuditEvent], violations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Assess compliance status based on events and violations."""
        total_events = len(events)
        total_violations = len(violations)
        
        # Calculate compliance score
        if total_events == 0:
            compliance_score = 100.0
        else:
            violation_rate = total_violations / total_events
            compliance_score = max(0.0, 100.0 - (violation_rate * 100))
        
        # Assess severity distribution
        critical_violations = sum(1 for v in violations if v.get('severity') == 'critical')
        high_violations = sum(1 for v in violations if v.get('severity') == 'high')
        
        compliance_level = "excellent" if compliance_score >= 95 else \
                          "good" if compliance_score >= 85 else \
                          "fair" if compliance_score >= 70 else "poor"
        
        return {
            "compliance_score": compliance_score,
            "compliance_level": compliance_level,
            "total_events": total_events,
            "total_violations": total_violations,
            "critical_violations": critical_violations,
            "high_violations": high_violations,
            "violation_rate": (total_violations / max(total_events, 1)) * 100
        }
    
    def close(self):
        """Close audit logger and cleanup."""
        # Log session end
        self.log_audit_event(
            event_type=AuditEventType.SYSTEM_EVENT,
            action="session_end",
            result="success",
            details={"session_id": self.session_id, "events_logged": len(self.audit_events)}
        )
        
        # Close handlers
        if self.audit_handler:
            self.audit_handler.close()
            self.audit_logger.removeHandler(self.audit_handler)


class SecurityScanner:
    """Security scanning and vulnerability assessment."""
    
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path("./security-scan-output")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        self.validator = InputValidator()
        self.audit_logger = AuditLogger(self.output_dir / "audit")
    
    def run_comprehensive_security_assessment(self) -> SecurityAssessmentResult:
        """
        Run comprehensive security assessment.
        
        Returns:
            Security assessment result
        """
        self.logger.info("Starting comprehensive security assessment")
        
        assessment_id = f"security_assessment_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        start_time = datetime.now()
        
        try:
            findings = {}
            vulnerabilities = []
            recommendations = []
            
            # 1. Code security scan
            self.logger.info("Running code security scan")
            code_findings = self._scan_code_security()
            findings["code_security"] = code_findings
            vulnerabilities.extend(code_findings.get("vulnerabilities", []))
            recommendations.extend(code_findings.get("recommendations", []))
            
            # 2. Configuration security scan
            self.logger.info("Running configuration security scan")
            config_findings = self._scan_configuration_security()
            findings["configuration_security"] = config_findings
            vulnerabilities.extend(config_findings.get("vulnerabilities", []))
            recommendations.extend(config_findings.get("recommendations", []))
            
            # 3. Dependency security scan
            self.logger.info("Running dependency security scan")
            dependency_findings = self._scan_dependency_security()
            findings["dependency_security"] = dependency_findings
            vulnerabilities.extend(dependency_findings.get("vulnerabilities", []))
            recommendations.extend(dependency_findings.get("recommendations", []))
            
            # 4. File system security scan
            self.logger.info("Running file system security scan")
            filesystem_findings = self._scan_filesystem_security()
            findings["filesystem_security"] = filesystem_findings
            vulnerabilities.extend(filesystem_findings.get("vulnerabilities", []))
            recommendations.extend(filesystem_findings.get("recommendations", []))
            
            # 5. Input validation assessment
            self.logger.info("Running input validation assessment")
            input_findings = self._assess_input_validation()
            findings["input_validation"] = input_findings
            vulnerabilities.extend(input_findings.get("vulnerabilities", []))
            recommendations.extend(input_findings.get("recommendations", []))
            
            # Categorize vulnerabilities by severity
            critical_issues = sum(1 for v in vulnerabilities if v.get("severity") == "critical")
            high_issues = sum(1 for v in vulnerabilities if v.get("severity") == "high")
            medium_issues = sum(1 for v in vulnerabilities if v.get("severity") == "medium")
            low_issues = sum(1 for v in vulnerabilities if v.get("severity") == "low")
            
            # Calculate overall security score
            total_issues = len(vulnerabilities)
            if total_issues == 0:
                security_score = 100.0
            else:
                # Weight issues by severity
                weighted_score = (
                    critical_issues * 25 +  # Critical issues heavily penalized
                    high_issues * 10 +
                    medium_issues * 5 +
                    low_issues * 1
                )
                security_score = max(0.0, 100.0 - weighted_score)
            
            # Calculate compliance score
            compliance_score = self._calculate_compliance_score(findings)
            
            # Generate audit report
            audit_report = self.audit_logger.generate_audit_report()
            
            result = SecurityAssessmentResult(
                assessment_id=assessment_id,
                timestamp=start_time,
                overall_security_score=security_score,
                vulnerabilities_found=total_issues,
                critical_issues=critical_issues,
                high_issues=high_issues,
                medium_issues=medium_issues,
                low_issues=low_issues,
                compliance_score=compliance_score,
                audit_events_analyzed=audit_report["summary"]["total_events"],
                security_violations=audit_report["summary"]["total_violations"],
                recommendations=recommendations,
                detailed_findings=findings
            )
            
            # Save assessment result
            self._save_assessment_result(result)
            
            # Log completion
            self.audit_logger.log_audit_event(
                event_type=AuditEventType.SYSTEM_EVENT,
                action="security_assessment_completed",
                result="success",
                details={
                    "assessment_id": assessment_id,
                    "security_score": security_score,
                    "vulnerabilities_found": total_issues
                }
            )
            
            self.logger.info(f"Security assessment completed: {security_score:.1f}% security score, {total_issues} vulnerabilities found")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Security assessment failed: {e}")
            
            # Log failure
            self.audit_logger.log_audit_event(
                event_type=AuditEventType.ERROR,
                action="security_assessment_failed",
                result="error",
                details={"error": str(e)}
            )
            
            raise
        
        finally:
            self.audit_logger.close()
    
    def _scan_code_security(self) -> Dict[str, Any]:
        """Scan code for security vulnerabilities."""
        findings = {
            "vulnerabilities": [],
            "recommendations": [],
            "scan_summary": {}
        }
        
        try:
            # Scan Python files for common security issues
            python_files = list(Path(".").rglob("*.py"))
            
            security_patterns = [
                {
                    "pattern": r"eval\s*\(",
                    "severity": "critical",
                    "description": "Use of eval() function - potential code injection",
                    "recommendation": "Replace eval() with safer alternatives like ast.literal_eval()"
                },
                {
                    "pattern": r"exec\s*\(",
                    "severity": "critical", 
                    "description": "Use of exec() function - potential code injection",
                    "recommendation": "Avoid exec() or use in controlled environment"
                },
                {
                    "pattern": r"subprocess\.call\s*\([^)]*shell\s*=\s*True",
                    "severity": "high",
                    "description": "Subprocess call with shell=True - potential command injection",
                    "recommendation": "Use shell=False and pass arguments as list"
                },
                {
                    "pattern": r"os\.system\s*\(",
                    "severity": "high",
                    "description": "Use of os.system() - potential command injection",
                    "recommendation": "Use subprocess module instead"
                },
                {
                    "pattern": r"pickle\.loads?\s*\(",
                    "severity": "medium",
                    "description": "Use of pickle - potential deserialization vulnerability",
                    "recommendation": "Use safer serialization formats like JSON"
                },
                {
                    "pattern": r"random\.random\s*\(",
                    "severity": "low",
                    "description": "Use of non-cryptographic random - not suitable for security",
                    "recommendation": "Use secrets module for cryptographic randomness"
                }
            ]
            
            issues_found = 0
            
            for python_file in python_files:
                try:
                    content = python_file.read_text()
                    
                    for pattern_info in security_patterns:
                        matches = re.finditer(pattern_info["pattern"], content, re.IGNORECASE)
                        
                        for match in matches:
                            line_num = content[:match.start()].count('\n') + 1
                            
                            vulnerability = {
                                "type": "code_security",
                                "severity": pattern_info["severity"],
                                "file": str(python_file),
                                "line": line_num,
                                "description": pattern_info["description"],
                                "code_snippet": match.group(0),
                                "recommendation": pattern_info["recommendation"]
                            }
                            
                            findings["vulnerabilities"].append(vulnerability)
                            issues_found += 1
                            
                except Exception as e:
                    self.logger.warning(f"Failed to scan {python_file}: {e}")
            
            findings["scan_summary"] = {
                "files_scanned": len(python_files),
                "issues_found": issues_found,
                "patterns_checked": len(security_patterns)
            }
            
            if issues_found == 0:
                findings["recommendations"].append("Code security scan completed - no major issues found")
            else:
                findings["recommendations"].append(f"Address {issues_found} code security issues found")
                
        except Exception as e:
            self.logger.error(f"Code security scan failed: {e}")
            findings["scan_summary"]["error"] = str(e)
        
        return findings
    
    def _scan_configuration_security(self) -> Dict[str, Any]:
        """Scan configuration for security issues."""
        findings = {
            "vulnerabilities": [],
            "recommendations": [],
            "scan_summary": {}
        }
        
        try:
            issues_found = 0
            
            # Check for sensitive files with weak permissions
            sensitive_patterns = [
                "*.key", "*.pem", "*.p12", "*.pfx",
                "*.env", ".env*", "config.json", "secrets.json"
            ]
            
            for pattern in sensitive_patterns:
                for file_path in Path(".").rglob(pattern):
                    if file_path.is_file():
                        stat_info = file_path.stat()
                        permissions = oct(stat_info.st_mode)[-3:]
                        
                        # Check if file is readable by others
                        if int(permissions[2]) > 0:
                            vulnerability = {
                                "type": "configuration_security",
                                "severity": "high",
                                "file": str(file_path),
                                "description": f"Sensitive file has weak permissions: {permissions}",
                                "recommendation": "Set restrictive permissions (600 or 700)"
                            }
                            
                            findings["vulnerabilities"].append(vulnerability)
                            issues_found += 1
            
            # Check for hardcoded secrets in configuration files
            config_files = list(Path(".").rglob("*.json")) + list(Path(".").rglob("*.yaml")) + list(Path(".").rglob("*.yml"))
            
            secret_patterns = [
                r"password\s*[:=]\s*['\"][^'\"]{3,}['\"]",
                r"api_key\s*[:=]\s*['\"][^'\"]{10,}['\"]",
                r"secret\s*[:=]\s*['\"][^'\"]{8,}['\"]",
                r"token\s*[:=]\s*['\"][^'\"]{10,}['\"]"
            ]
            
            for config_file in config_files:
                try:
                    content = config_file.read_text()
                    
                    for pattern in secret_patterns:
                        matches = re.finditer(pattern, content, re.IGNORECASE)
                        
                        for match in matches:
                            line_num = content[:match.start()].count('\n') + 1
                            
                            vulnerability = {
                                "type": "configuration_security",
                                "severity": "critical",
                                "file": str(config_file),
                                "line": line_num,
                                "description": "Potential hardcoded secret in configuration",
                                "recommendation": "Move secrets to environment variables or secure secret management"
                            }
                            
                            findings["vulnerabilities"].append(vulnerability)
                            issues_found += 1
                            
                except Exception as e:
                    self.logger.warning(f"Failed to scan config file {config_file}: {e}")
            
            findings["scan_summary"] = {
                "sensitive_files_checked": len(list(Path(".").rglob("*"))),
                "config_files_scanned": len(config_files),
                "issues_found": issues_found
            }
            
            if issues_found == 0:
                findings["recommendations"].append("Configuration security scan completed - no issues found")
            else:
                findings["recommendations"].append(f"Address {issues_found} configuration security issues")
                
        except Exception as e:
            self.logger.error(f"Configuration security scan failed: {e}")
            findings["scan_summary"]["error"] = str(e)
        
        return findings
    
    def _scan_dependency_security(self) -> Dict[str, Any]:
        """Scan dependencies for known vulnerabilities."""
        findings = {
            "vulnerabilities": [],
            "recommendations": [],
            "scan_summary": {}
        }
        
        try:
            # Check if requirements files exist
            req_files = ["requirements.txt", "requirements-orchestrator.txt", "setup.py", "pyproject.toml"]
            found_req_files = [f for f in req_files if Path(f).exists()]
            
            if not found_req_files:
                findings["recommendations"].append("No Python requirements files found - dependency scan skipped")
                findings["scan_summary"] = {"requirements_files": 0, "dependencies_checked": 0}
                return findings
            
            # Try to run safety check if available
            try:
                result = subprocess.run(
                    ["python", "-m", "safety", "check", "--json"],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode == 0:
                    # Parse safety output
                    try:
                        safety_data = json.loads(result.stdout)
                        
                        for vuln in safety_data:
                            vulnerability = {
                                "type": "dependency_security",
                                "severity": "high",
                                "package": vuln.get("package"),
                                "version": vuln.get("installed_version"),
                                "vulnerability_id": vuln.get("vulnerability_id"),
                                "description": vuln.get("advisory"),
                                "recommendation": f"Update to version {vuln.get('safe_versions', 'latest')}"
                            }
                            
                            findings["vulnerabilities"].append(vulnerability)
                        
                        findings["scan_summary"]["safety_check"] = "completed"
                        
                    except json.JSONDecodeError:
                        findings["scan_summary"]["safety_check"] = "failed_to_parse"
                        
                else:
                    findings["scan_summary"]["safety_check"] = "failed"
                    
            except (subprocess.TimeoutExpired, FileNotFoundError):
                findings["recommendations"].append("Install 'safety' package for dependency vulnerability scanning")
                findings["scan_summary"]["safety_check"] = "not_available"
            
            # Basic dependency analysis
            dependencies_found = 0
            
            for req_file in found_req_files:
                if Path(req_file).exists():
                    try:
                        content = Path(req_file).read_text()
                        
                        # Count dependencies
                        lines = [line.strip() for line in content.split('\n') if line.strip() and not line.startswith('#')]
                        dependencies_found += len(lines)
                        
                        # Check for unpinned versions
                        unpinned = [line for line in lines if '==' not in line and '>=' not in line and line]
                        
                        if unpinned:
                            vulnerability = {
                                "type": "dependency_security",
                                "severity": "medium",
                                "file": req_file,
                                "description": f"Unpinned dependencies found: {len(unpinned)} packages",
                                "recommendation": "Pin dependency versions for reproducible builds"
                            }
                            
                            findings["vulnerabilities"].append(vulnerability)
                            
                    except Exception as e:
                        self.logger.warning(f"Failed to analyze {req_file}: {e}")
            
            findings["scan_summary"] = {
                "requirements_files": len(found_req_files),
                "dependencies_checked": dependencies_found,
                "vulnerabilities_found": len(findings["vulnerabilities"])
            }
            
            if len(findings["vulnerabilities"]) == 0:
                findings["recommendations"].append("Dependency security scan completed - no known vulnerabilities")
            else:
                findings["recommendations"].append(f"Address {len(findings['vulnerabilities'])} dependency security issues")
                
        except Exception as e:
            self.logger.error(f"Dependency security scan failed: {e}")
            findings["scan_summary"]["error"] = str(e)
        
        return findings
    
    def _scan_filesystem_security(self) -> Dict[str, Any]:
        """Scan file system for security issues."""
        findings = {
            "vulnerabilities": [],
            "recommendations": [],
            "scan_summary": {}
        }
        
        try:
            issues_found = 0
            
            # Check for world-writable files
            for file_path in Path(".").rglob("*"):
                if file_path.is_file():
                    try:
                        stat_info = file_path.stat()
                        permissions = oct(stat_info.st_mode)[-3:]
                        
                        # Check if file is world-writable
                        if int(permissions[2]) >= 2:
                            vulnerability = {
                                "type": "filesystem_security",
                                "severity": "medium",
                                "file": str(file_path),
                                "description": f"World-writable file: {permissions}",
                                "recommendation": "Remove write permissions for others"
                            }
                            
                            findings["vulnerabilities"].append(vulnerability)
                            issues_found += 1
                            
                    except Exception:
                        continue  # Skip files we can't stat
            
            # Check for executable files in unusual locations
            executable_extensions = [".exe", ".bat", ".cmd", ".sh", ".ps1"]
            
            for ext in executable_extensions:
                for file_path in Path(".").rglob(f"*{ext}"):
                    if file_path.is_file():
                        # Check if executable is in a data directory
                        path_parts = file_path.parts
                        suspicious_dirs = ["data", "uploads", "temp", "tmp", "cache"]
                        
                        if any(suspicious_dir in path_parts for suspicious_dir in suspicious_dirs):
                            vulnerability = {
                                "type": "filesystem_security",
                                "severity": "high",
                                "file": str(file_path),
                                "description": "Executable file in data directory",
                                "recommendation": "Review if executable should be in this location"
                            }
                            
                            findings["vulnerabilities"].append(vulnerability)
                            issues_found += 1
            
            findings["scan_summary"] = {
                "files_scanned": len(list(Path(".").rglob("*"))),
                "issues_found": issues_found
            }
            
            if issues_found == 0:
                findings["recommendations"].append("File system security scan completed - no issues found")
            else:
                findings["recommendations"].append(f"Address {issues_found} file system security issues")
                
        except Exception as e:
            self.logger.error(f"File system security scan failed: {e}")
            findings["scan_summary"]["error"] = str(e)
        
        return findings
    
    def _assess_input_validation(self) -> Dict[str, Any]:
        """Assess input validation implementation."""
        findings = {
            "vulnerabilities": [],
            "recommendations": [],
            "scan_summary": {}
        }
        
        try:
            # Check if input validation is implemented
            validation_score = 0
            
            # Look for input validation patterns in code
            python_files = list(Path(".").rglob("*.py"))
            validation_patterns = [
                r"validate.*input",
                r"sanitize.*input", 
                r"input.*validation",
                r"InputValidator",
                r"re\.match\s*\(",
                r"re\.search\s*\("
            ]
            
            files_with_validation = 0
            
            for python_file in python_files:
                try:
                    content = python_file.read_text()
                    
                    has_validation = any(
                        re.search(pattern, content, re.IGNORECASE)
                        for pattern in validation_patterns
                    )
                    
                    if has_validation:
                        files_with_validation += 1
                        
                except Exception:
                    continue
            
            if len(python_files) > 0:
                validation_coverage = (files_with_validation / len(python_files)) * 100
            else:
                validation_coverage = 0
            
            if validation_coverage < 20:
                vulnerability = {
                    "type": "input_validation",
                    "severity": "high",
                    "description": f"Low input validation coverage: {validation_coverage:.1f}%",
                    "recommendation": "Implement comprehensive input validation across the application"
                }
                findings["vulnerabilities"].append(vulnerability)
            
            elif validation_coverage < 50:
                vulnerability = {
                    "type": "input_validation",
                    "severity": "medium",
                    "description": f"Moderate input validation coverage: {validation_coverage:.1f}%",
                    "recommendation": "Increase input validation coverage"
                }
                findings["vulnerabilities"].append(vulnerability)
            
            # Test the validator if it exists
            validator_violations = self.validator.violation_count
            
            findings["scan_summary"] = {
                "python_files_scanned": len(python_files),
                "files_with_validation": files_with_validation,
                "validation_coverage": validation_coverage,
                "validator_violations": validator_violations
            }
            
            if len(findings["vulnerabilities"]) == 0:
                findings["recommendations"].append("Input validation assessment completed - good coverage detected")
            else:
                findings["recommendations"].append("Improve input validation implementation")
                
        except Exception as e:
            self.logger.error(f"Input validation assessment failed: {e}")
            findings["scan_summary"]["error"] = str(e)
        
        return findings
    
    def _calculate_compliance_score(self, findings: Dict[str, Any]) -> float:
        """Calculate compliance score based on findings."""
        total_score = 100.0
        
        # Deduct points for each category
        for category, category_findings in findings.items():
            vulnerabilities = category_findings.get("vulnerabilities", [])
            
            for vuln in vulnerabilities:
                severity = vuln.get("severity", "low")
                
                if severity == "critical":
                    total_score -= 15
                elif severity == "high":
                    total_score -= 10
                elif severity == "medium":
                    total_score -= 5
                elif severity == "low":
                    total_score -= 2
        
        return max(0.0, total_score)
    
    def _save_assessment_result(self, result: SecurityAssessmentResult) -> None:
        """Save security assessment result to file."""
        # Save JSON report
        json_path = self.output_dir / f"security_assessment_{result.assessment_id}.json"
        with open(json_path, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
        
        # Save text summary
        text_path = self.output_dir / f"security_summary_{result.assessment_id}.txt"
        with open(text_path, 'w') as f:
            f.write(self._format_security_summary(result))
        
        self.logger.info(f"Security assessment results saved to {json_path} and {text_path}")
    
    def _format_security_summary(self, result: SecurityAssessmentResult) -> str:
        """Format security assessment result as text summary."""
        lines = [
            "=" * 80,
            "CLI WORKFLOW HARNESS - SECURITY ASSESSMENT RESULTS",
            "=" * 80,
            f"Assessment ID: {result.assessment_id}",
            f"Timestamp: {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "SECURITY SCORES:",
            f"  Overall Security Score: {result.overall_security_score:.1f}%",
            f"  Compliance Score: {result.compliance_score:.1f}%",
            "",
            "VULNERABILITY SUMMARY:",
            f"  Total Vulnerabilities: {result.vulnerabilities_found}",
            f"  Critical Issues: {result.critical_issues}",
            f"  High Issues: {result.high_issues}",
            f"  Medium Issues: {result.medium_issues}",
            f"  Low Issues: {result.low_issues}",
            "",
            "AUDIT SUMMARY:",
            f"  Audit Events Analyzed: {result.audit_events_analyzed}",
            f"  Security Violations: {result.security_violations}",
            "",
            "RECOMMENDATIONS:",
        ]
        
        for i, rec in enumerate(result.recommendations, 1):
            lines.append(f"  {i}. {rec}")
        
        lines.extend([
            "",
            "=" * 80,
        ])
        
        return "\n".join(lines)


def main():
    """Main entry point for security hardening."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Security and reliability hardening for CLI workflow harness")
    parser.add_argument(
        '--output-dir', '-o',
        type=Path,
        default=Path('./security-output'),
        help='Output directory for security results'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        scanner = SecurityScanner(args.output_dir)
        result = scanner.run_comprehensive_security_assessment()
        
        print(f"\nSecurity Assessment Completed:")
        print(f"  Security Score: {result.overall_security_score:.1f}%")
        print(f"  Compliance Score: {result.compliance_score:.1f}%")
        print(f"  Vulnerabilities Found: {result.vulnerabilities_found}")
        print(f"  Critical Issues: {result.critical_issues}")
        
        # Exit with appropriate code
        exit_code = 0 if result.overall_security_score >= 80 else 1
        sys.exit(exit_code)
        
    except Exception as e:
        logging.error(f"Security assessment failed: {e}")
        sys.exit(2)


if __name__ == '__main__':
    main()