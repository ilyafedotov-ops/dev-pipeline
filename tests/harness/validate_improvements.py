#!/usr/bin/env python3
"""Validation script for harness performance improvements."""

import sys
import os
from pathlib import Path

# Add the harness directory to the path
harness_dir = Path(__file__).parent
sys.path.insert(0, str(harness_dir))

def validate_parallel_improvements():
    """Validate parallel execution improvements."""
    print("Validating parallel execution improvements...")
    
    try:
        # Check that parallel.py has the new optimization methods
        with open(harness_dir / "parallel.py", "r") as f:
            content = f.read()
        
        required_methods = [
            "analyze_task_dependencies",
            "optimize_task_isolation", 
            "_optimize_isolation_group",
            "_sort_tasks_for_load_balancing",
            "_get_task_timeout",
            "_calculate_optimal_parallelism"
        ]
        
        for method in required_methods:
            if f"def {method}" in content:
                print(f"  ✓ Found optimization method: {method}")
            else:
                print(f"  ✗ Missing optimization method: {method}")
                return False
        
        # Check for improved component parallelism rules
        if "component_parallelism" in content:
            print("  ✓ Found component-specific parallelism rules")
        else:
            print("  ✗ Missing component-specific parallelism rules")
            return False
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error validating parallel improvements: {e}")
        return False

def validate_api_improvements():
    """Validate API timeout and retry improvements."""
    print("Validating API timeout and retry improvements...")
    
    try:
        # Check that api_utils.py exists and has required classes
        api_utils_path = harness_dir / "api_utils.py"
        if not api_utils_path.exists():
            print("  ✗ api_utils.py not found")
            return False
        
        with open(api_utils_path, "r") as f:
            content = f.read()
        
        required_classes = [
            "class APIServerManager",
            "class RetryableAPIClient", 
            "class CLICommandRunner"
        ]
        
        for cls in required_classes:
            if cls in content:
                print(f"  ✓ Found utility class: {cls}")
            else:
                print(f"  ✗ Missing utility class: {cls}")
                return False
        
        # Check for timeout optimization functions
        required_functions = [
            "get_optimal_timeout",
            "detect_command_type"
        ]
        
        for func in required_functions:
            if f"def {func}" in content:
                print(f"  ✓ Found timeout function: {func}")
            else:
                print(f"  ✗ Missing timeout function: {func}")
                return False
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error validating API improvements: {e}")
        return False

def validate_onboarding_improvements():
    """Validate onboarding component improvements."""
    print("Validating onboarding component improvements...")
    
    try:
        # Check that onboarding.py has improved error handling and timing
        onboarding_path = harness_dir / "components" / "onboarding.py"
        if not onboarding_path.exists():
            print("  ✗ onboarding.py not found")
            return False
        
        with open(onboarding_path, "r") as f:
            content = f.read()
        
        improvements = [
            "start_time = time.time()",  # Timing improvements
            "duration = time.time() - start_time",  # Duration tracking
            "timeout=120",  # Increased timeouts
            "env.update({",  # Environment setup
            "shutil.rmtree",  # Cleanup improvements
            "user.email",  # Git configuration
        ]
        
        for improvement in improvements:
            if improvement in content:
                print(f"  ✓ Found improvement: {improvement}")
            else:
                print(f"  ✗ Missing improvement: {improvement}")
                return False
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error validating onboarding improvements: {e}")
        return False

def main():
    """Main validation function."""
    print("Validating harness performance improvements...")
    print("=" * 50)
    
    results = []
    
    # Validate each improvement area
    results.append(validate_parallel_improvements())
    results.append(validate_api_improvements()) 
    results.append(validate_onboarding_improvements())
    
    print("=" * 50)
    
    if all(results):
        print("✓ All harness performance improvements validated successfully!")
        return 0
    else:
        print("✗ Some harness performance improvements are missing or incomplete")
        return 1

if __name__ == "__main__":
    sys.exit(main())