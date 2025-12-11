#!/usr/bin/env python3
"""
Security integration for CLI workflow harness.

This script integrates security hardening features into the existing harness
infrastructure, providing secure execution context and monitoring.
"""

import sys
import logging
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from contextlib import contextmanager

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.harness.security import (
    InputValidator, SecretManager, AuditLogger, SecurityScanner,
    SecurityLevel, AuditEventType
)
from tests.harness.config import HarnessConfig


class SecureHarnessContext:
    """Secure execution context for harness operations."""
    
    def __init__(self, config: HarnessConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize security components
        self.input_validator = InputValidator()
        self.secret_manager = SecretManager()
        self.audit_logger = AuditLogger(config.output_path / "audit")
        
        # Security configuration
        self.security_enabled = True
        self.allowed_commands = {
            "git", "python", "pip", "pytest", "black", "flake8", "mypy",
            "docker", "docker-compose", "npm", "node", "yarn"
        }
        
        # Log security context initialization
        self.audit_logger.log_audit_event(
            event_type=AuditEventType.SYSTEM_EVENT,
            action="secure_context_initialized",
            result="success",
            details={
                "security_enabled": self.security_enabled,
                "allowed_commands": list(self.allowed_commands)
            }
        )
    
    @contextmanager
    def secure_execution(self, operation_name: str, user_context: str = None):
        """Context manager for secure operation execution."""
        operation_id = f"{operation_name}_{id(self)}"
        
        # Log operation start
        self.audit_logger.log_audit_event(
            event_type=AuditEventType.SYSTEM_EVENT,
            action=f"operation_start_{operation_name}",
            result="started",
            user_context=user_context,
            details={"operation_id": operation_id}
        )
        
        try:
            yield self
            
            # Log successful completion
            self.audit_logger.log_audit_event(
                event_type=AuditEventType.SYSTEM_EVENT,
                action=f"operation_complete_{operation_name}",
                result="success",
                user_context=user_context,
                details={"operation_id": operation_id}
            )
            
        except Exception as e:
            # Log operation failure
            self.audit_logger.log_audit_event(
                event_type=AuditEventType.ERROR,
                action=f"operation_failed_{operation_name}",
                result="error",
                user_context=user_context,
                severity=SecurityLevel.HIGH,
                details={
                    "operation_id": operation_id,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            raise
    
    def validate_input(self, input_value: str, input_type: str = "string", 
                      context: str = "unknown") -> tuple[bool, str, Optional[str]]:
        """Validate input using security validator."""
        if not self.security_enabled:
            return True, input_value, None
        
        try:
            if input_type == "string":
                is_valid, sanitized, error = self.input_validator.validate_string_input(
                    input_value, context=context
                )
            elif input_type == "path":
                is_valid, sanitized_path, error = self.input_validator.validate_path_input(
                    input_value, base_path=Path.cwd()
                )
                sanitized = str(sanitized_path) if is_valid else ""
            elif input_type == "command":
                is_valid, sanitized, error = self.input_validator.validate_command_input(
                    input_value, allowed_commands=self.allowed_commands
                )
            else:
                is_valid, sanitized, error = True, input_value, None
            
            if not is_valid:
                # Log security violation
                self.audit_logger.log_security_violation(
                    violation_type="input_validation_failure",
                    description=f"Invalid {input_type} input in {context}: {error}",
                    severity=SecurityLevel.MEDIUM,
                    details={
                        "input_type": input_type,
                        "context": context,
                        "original_input": input_value[:100],  # Truncate for logging
                        "error": error
                    }
                )
            
            return is_valid, sanitized, error
            
        except Exception as e:
            self.logger.error(f"Input validation failed: {e}")
            return False, "", f"Validation error: {e}"
    
    def validate_file_access(self, file_path: Path, operation: str = "read") -> bool:
        """Validate file access permissions."""
        if not self.security_enabled:
            return True
        
        try:
            # Resolve path to prevent traversal
            resolved_path = file_path.resolve()
            
            # Check if path is within allowed directories
            allowed_bases = [
                Path.cwd().resolve(),
                Path.home().resolve() / ".tasksgodzilla",
                Path("/tmp").resolve()
            ]
            
            path_allowed = any(
                str(resolved_path).startswith(str(base))
                for base in allowed_bases
            )
            
            if not path_allowed:
                self.audit_logger.log_security_violation(
                    violation_type="unauthorized_file_access",
                    description=f"Attempted {operation} access to unauthorized path: {resolved_path}",
                    severity=SecurityLevel.HIGH,
                    details={
                        "requested_path": str(file_path),
                        "resolved_path": str(resolved_path),
                        "operation": operation
                    }
                )
                return False
            
            # Check file permissions
            if operation == "read" and not resolved_path.exists():
                return False
            
            if operation == "write":
                parent_dir = resolved_path.parent
                if not parent_dir.exists():
                    try:
                        parent_dir.mkdir(parents=True, exist_ok=True)
                    except Exception:
                        return False
            
            # Log authorized access
            self.audit_logger.log_audit_event(
                event_type=AuditEventType.DATA_ACCESS,
                action=f"file_{operation}",
                result="authorized",
                resource=str(resolved_path),
                details={"operation": operation}
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"File access validation failed: {e}")
            return False
    
    def secure_command_execution(self, command: str, cwd: Path = None) -> tuple[bool, str]:
        """Securely execute a command with validation."""
        if not self.security_enabled:
            return True, "Security disabled"
        
        # Validate command
        is_valid, sanitized_command, error = self.validate_input(
            command, input_type="command", context="command_execution"
        )
        
        if not is_valid:
            return False, f"Command validation failed: {error}"
        
        # Validate working directory
        if cwd:
            if not self.validate_file_access(cwd, "read"):
                return False, "Working directory access denied"
        
        # Log command execution attempt
        self.audit_logger.log_audit_event(
            event_type=AuditEventType.SYSTEM_EVENT,
            action="command_execution",
            result="authorized",
            details={
                "command": sanitized_command,
                "working_directory": str(cwd) if cwd else None
            }
        )
        
        return True, "Command authorized"
    
    def get_secret(self, key: str) -> Optional[str]:
        """Retrieve a secret securely."""
        try:
            # Validate key
            is_valid, sanitized_key, error = self.validate_input(
                key, input_type="string", context="secret_retrieval"
            )
            
            if not is_valid:
                return None
            
            # Retrieve secret
            secret_value = self.secret_manager.retrieve_secret(sanitized_key)
            
            # Log access attempt
            self.audit_logger.log_audit_event(
                event_type=AuditEventType.DATA_ACCESS,
                action="secret_retrieval",
                result="success" if secret_value else "not_found",
                resource=sanitized_key,
                details={"key": sanitized_key}
            )
            
            return secret_value
            
        except Exception as e:
            self.logger.error(f"Secret retrieval failed: {e}")
            return None
    
    def set_secret(self, key: str, value: str, description: str = "") -> bool:
        """Store a secret securely."""
        try:
            # Validate inputs
            key_valid, sanitized_key, key_error = self.validate_input(
                key, input_type="string", context="secret_storage"
            )
            
            if not key_valid:
                return False
            
            # Store secret
            success = self.secret_manager.store_secret(
                sanitized_key, value, description
            )
            
            # Log storage attempt
            self.audit_logger.log_audit_event(
                event_type=AuditEventType.DATA_ACCESS,
                action="secret_storage",
                result="success" if success else "failed",
                resource=sanitized_key,
                details={
                    "key": sanitized_key,
                    "description": description
                }
            )
            
            return success
            
        except Exception as e:
            self.logger.error(f"Secret storage failed: {e}")
            return False
    
    def cleanup_expired_secrets(self) -> int:
        """Clean up expired secrets."""
        try:
            cleaned_count = self.secret_manager.cleanup_expired_secrets()
            
            # Log cleanup
            self.audit_logger.log_audit_event(
                event_type=AuditEventType.SYSTEM_EVENT,
                action="secret_cleanup",
                result="success",
                details={"secrets_cleaned": cleaned_count}
            )
            
            return cleaned_count
            
        except Exception as e:
            self.logger.error(f"Secret cleanup failed: {e}")
            return 0
    
    def generate_security_report(self) -> Dict[str, Any]:
        """Generate security report for current session."""
        try:
            # Generate audit report
            audit_report = self.audit_logger.generate_audit_report()
            
            # Get secret manager statistics
            secrets_list = self.secret_manager.list_secrets()
            
            # Get input validator statistics
            validator_violations = self.input_validator.violation_count
            
            security_report = {
                "session_summary": {
                    "security_enabled": self.security_enabled,
                    "validator_violations": validator_violations,
                    "secrets_managed": len(secrets_list),
                    "allowed_commands": list(self.allowed_commands)
                },
                "audit_summary": audit_report["summary"],
                "compliance_status": audit_report["compliance_status"],
                "recent_violations": audit_report.get("violations", [])[:5],  # Last 5 violations
                "recommendations": self._generate_security_recommendations(
                    validator_violations, len(secrets_list), audit_report
                )
            }
            
            return security_report
            
        except Exception as e:
            self.logger.error(f"Security report generation failed: {e}")
            return {"error": str(e)}
    
    def _generate_security_recommendations(self, validator_violations: int, 
                                         secrets_count: int,
                                         audit_report: Dict[str, Any]) -> List[str]:
        """Generate security recommendations based on current state."""
        recommendations = []
        
        # Input validation recommendations
        if validator_violations > 0:
            recommendations.append(
                f"Address {validator_violations} input validation violations detected"
            )
        
        # Secret management recommendations
        if secrets_count == 0:
            recommendations.append(
                "Consider using secret management for sensitive configuration"
            )
        elif secrets_count > 10:
            recommendations.append(
                f"Review {secrets_count} stored secrets and clean up unused ones"
            )
        
        # Audit recommendations
        compliance_score = audit_report.get("compliance_status", {}).get("compliance_score", 100)
        if compliance_score < 90:
            recommendations.append(
                f"Improve compliance score: {compliance_score:.1f}% (target: >90%)"
            )
        
        violations_count = audit_report.get("summary", {}).get("total_violations", 0)
        if violations_count > 0:
            recommendations.append(
                f"Investigate and address {violations_count} security violations"
            )
        
        if not recommendations:
            recommendations.append("Security posture is good - continue monitoring")
        
        return recommendations
    
    def close(self):
        """Close security context and cleanup."""
        try:
            # Generate final security report
            security_report = self.generate_security_report()
            
            # Log session end
            self.audit_logger.log_audit_event(
                event_type=AuditEventType.SYSTEM_EVENT,
                action="secure_context_closed",
                result="success",
                details={
                    "validator_violations": security_report["session_summary"]["validator_violations"],
                    "secrets_managed": security_report["session_summary"]["secrets_managed"]
                }
            )
            
            # Close audit logger
            self.audit_logger.close()
            
            self.logger.info("Secure harness context closed")
            
        except Exception as e:
            self.logger.error(f"Error closing secure context: {e}")


class SecurityHardeningManager:
    """Manager for security hardening features in the harness."""
    
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path("./security-hardening-output")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
    
    def apply_security_hardening(self, config: HarnessConfig) -> HarnessConfig:
        """Apply security hardening to harness configuration."""
        self.logger.info("Applying security hardening to harness configuration")
        
        # Create hardened configuration
        hardened_config = HarnessConfig(
            mode=config.mode,
            components=config.components,
            test_data_path=config.test_data_path,
            output_path=self.output_dir / "hardened-output",
            verbose=config.verbose,
            parallel=config.parallel,
            timeout=min(config.timeout, 3600),  # Cap timeout at 1 hour
            max_workers=min(config.max_workers, 8),  # Cap workers for security
        )
        
        # Set secure environment variables
        self._set_secure_environment()
        
        # Create secure output directory
        hardened_config.output_path.mkdir(parents=True, exist_ok=True)
        
        # Set restrictive permissions
        try:
            hardened_config.output_path.chmod(0o750)
        except Exception as e:
            self.logger.warning(f"Could not set directory permissions: {e}")
        
        self.logger.info("Security hardening applied to configuration")
        
        return hardened_config
    
    def _set_secure_environment(self):
        """Set secure environment variables."""
        # Disable potentially dangerous environment variables
        dangerous_env_vars = [
            "PYTHONPATH",  # Could be used for code injection
            "LD_PRELOAD",  # Could be used for library injection
            "LD_LIBRARY_PATH",  # Could be used for library hijacking
        ]
        
        for var in dangerous_env_vars:
            if var in os.environ:
                self.logger.warning(f"Removing potentially dangerous environment variable: {var}")
                del os.environ[var]
        
        # Set secure defaults
        os.environ["PYTHONDONTWRITEBYTECODE"] = "1"  # Don't write .pyc files
        os.environ["PYTHONHASHSEED"] = "random"  # Randomize hash seed
        os.environ["TASKSGODZILLA_SECURITY_ENABLED"] = "true"
    
    def run_security_assessment(self) -> Dict[str, Any]:
        """Run comprehensive security assessment."""
        self.logger.info("Running security assessment")
        
        try:
            scanner = SecurityScanner(self.output_dir / "security-scan")
            result = scanner.run_comprehensive_security_assessment()
            
            assessment_summary = {
                "assessment_id": result.assessment_id,
                "security_score": result.overall_security_score,
                "compliance_score": result.compliance_score,
                "vulnerabilities_found": result.vulnerabilities_found,
                "critical_issues": result.critical_issues,
                "high_issues": result.high_issues,
                "recommendations": result.recommendations[:5],  # Top 5 recommendations
                "production_ready": result.overall_security_score >= 80 and result.critical_issues == 0
            }
            
            self.logger.info(f"Security assessment completed: {result.overall_security_score:.1f}% security score")
            
            return assessment_summary
            
        except Exception as e:
            self.logger.error(f"Security assessment failed: {e}")
            return {"error": str(e), "production_ready": False}
    
    def create_secure_harness_context(self, config: HarnessConfig) -> SecureHarnessContext:
        """Create a secure harness execution context."""
        # Apply security hardening to config
        hardened_config = self.apply_security_hardening(config)
        
        # Create secure context
        secure_context = SecureHarnessContext(hardened_config)
        
        self.logger.info("Secure harness context created")
        
        return secure_context


def main():
    """Main entry point for security integration testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Security integration for CLI workflow harness")
    parser.add_argument(
        '--output-dir', '-o',
        type=Path,
        default=Path('./security-integration-output'),
        help='Output directory for security integration results'
    )
    parser.add_argument(
        '--run-assessment',
        action='store_true',
        help='Run security assessment'
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
        manager = SecurityHardeningManager(args.output_dir)
        
        if args.run_assessment:
            # Run security assessment
            assessment = manager.run_security_assessment()
            
            print(f"\nSecurity Assessment Results:")
            print(f"  Security Score: {assessment.get('security_score', 0):.1f}%")
            print(f"  Compliance Score: {assessment.get('compliance_score', 0):.1f}%")
            print(f"  Vulnerabilities: {assessment.get('vulnerabilities_found', 0)}")
            print(f"  Critical Issues: {assessment.get('critical_issues', 0)}")
            print(f"  Production Ready: {'Yes' if assessment.get('production_ready', False) else 'No'}")
            
            if assessment.get('recommendations'):
                print("\nTop Recommendations:")
                for i, rec in enumerate(assessment['recommendations'], 1):
                    print(f"  {i}. {rec}")
        
        else:
            # Test secure context creation
            from tests.harness.models import HarnessMode
            
            test_config = HarnessConfig(
                mode=HarnessMode.SMOKE,
                components=["onboarding"],
                test_data_path=Path("demo_bootstrap"),
                output_path=args.output_dir / "test",
                verbose=args.verbose,
                parallel=False,
                timeout=300,
                max_workers=1,
            )
            
            # Create secure context
            secure_context = manager.create_secure_harness_context(test_config)
            
            # Test security features
            print("\nTesting security features:")
            
            # Test input validation
            valid, sanitized, error = secure_context.validate_input("test_input", "string", "test")
            print(f"  Input validation: {'✓' if valid else '✗'} - {sanitized if valid else error}")
            
            # Test command validation
            valid, message = secure_context.secure_command_execution("python --version")
            print(f"  Command validation: {'✓' if valid else '✗'} - {message}")
            
            # Test file access validation
            valid = secure_context.validate_file_access(Path("demo_bootstrap/README.md"), "read")
            print(f"  File access validation: {'✓' if valid else '✗'}")
            
            # Generate security report
            report = secure_context.generate_security_report()
            print(f"  Security report generated: {len(report.get('recommendations', []))} recommendations")
            
            # Close context
            secure_context.close()
            
            print("\nSecurity integration test completed successfully")
        
        sys.exit(0)
        
    except Exception as e:
        logging.error(f"Security integration failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()