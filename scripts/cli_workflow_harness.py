#!/usr/bin/env python3
"""
CLI Workflow Harness - Main entry point for comprehensive CLI workflow testing.

This script provides a command-line interface for running the CLI workflow harness
in various modes to validate the complete TasksGodzilla workflow from project 
onboarding through discovery, specs, protocol execution, and changes.
"""

import argparse
import logging
import sys
import json
from pathlib import Path
from typing import List, Optional

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.harness import CLIWorkflowHarness, HarnessConfig, HarnessMode
from tests.harness.models import HarnessStatus


def setup_logging(verbose: bool = False, log_file: Optional[Path] = None) -> None:
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=handlers
    )


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="CLI Workflow Harness - Comprehensive CLI workflow testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full workflow test
  %(prog)s --mode full

  # Run smoke tests with verbose output
  %(prog)s --mode smoke --verbose

  # Run specific components in parallel
  %(prog)s --mode component --components onboarding discovery --parallel

  # Run in CI mode with machine-readable output
  %(prog)s --mode ci --output-format junit --output-dir ./ci-reports

  # Run with custom configuration file
  %(prog)s --config harness-config.json

  # Run development mode with debugging
  %(prog)s --mode development --verbose --log-file harness.log
        """
    )
    
    # Execution mode
    parser.add_argument(
        '--mode', '-m',
        type=str,
        choices=[mode.value for mode in HarnessMode],
        default=HarnessMode.SMOKE.value,
        help='Test execution mode (default: %(default)s)'
    )
    
    # Component selection
    parser.add_argument(
        '--components', '-c',
        nargs='*',
        choices=[
            'onboarding', 'discovery', 'protocol', 'spec', 'quality',
            'cli_interface', 'tui_interface', 'api_integration', 
            'error_conditions', 'failure_detection'
        ],
        help='Specific components to test (default: all for mode)'
    )
    
    # Configuration
    parser.add_argument(
        '--config',
        type=Path,
        help='Configuration file path (JSON format)'
    )
    
    # Output options
    parser.add_argument(
        '--output-dir', '-o',
        type=Path,
        default=Path('./harness-output'),
        help='Output directory for reports (default: %(default)s)'
    )
    
    parser.add_argument(
        '--output-format',
        choices=['text', 'json', 'junit', 'all'],
        default='text',
        help='Output format for CI systems (default: %(default)s)'
    )
    
    # Execution options
    parser.add_argument(
        '--parallel', '-p',
        action='store_true',
        help='Enable parallel test execution'
    )
    
    parser.add_argument(
        '--max-workers',
        type=int,
        default=4,
        help='Maximum number of parallel workers (default: %(default)s)'
    )
    
    parser.add_argument(
        '--timeout',
        type=int,
        default=1800,
        help='Test execution timeout in seconds (default: %(default)s)'
    )
    
    # Logging options
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--log-file',
        type=Path,
        help='Log file path for detailed logging'
    )
    
    # Test data options
    parser.add_argument(
        '--test-data-path',
        type=Path,
        default=Path('./tests/harness/data'),
        help='Test data directory path (default: %(default)s)'
    )
    
    # CI-specific options
    parser.add_argument(
        '--ci',
        action='store_true',
        help='Force CI mode (non-interactive, machine-readable output)'
    )
    
    parser.add_argument(
        '--exit-on-failure',
        action='store_true',
        help='Exit with non-zero code on test failures'
    )
    
    return parser.parse_args()


def load_config_file(config_path: Path) -> dict:
    """Load configuration from JSON file."""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file not found: {config_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in configuration file: {e}")
        sys.exit(1)


def create_harness_config(args: argparse.Namespace) -> HarnessConfig:
    """Create harness configuration from command-line arguments."""
    # Load configuration file if provided
    config_data = {}
    if args.config:
        config_data = load_config_file(args.config)
    
    # Override with command-line arguments
    mode = HarnessMode.CI if args.ci else HarnessMode(args.mode)
    
    # Determine components
    components = args.components or config_data.get('components', [])
    
    # Create configuration
    config = HarnessConfig(
        mode=mode,
        components=components,
        test_data_path=args.test_data_path,
        output_path=args.output_dir,
        verbose=args.verbose or config_data.get('verbose', False),
        parallel=args.parallel or config_data.get('parallel', False),
        timeout=args.timeout or config_data.get('timeout', 1800),
        max_workers=args.max_workers or config_data.get('max_workers', 4),
    )
    
    return config


def generate_output_reports(harness: CLIWorkflowHarness, report, output_format: str) -> List[Path]:
    """Generate output reports in the specified format(s)."""
    generated_files = []
    
    if output_format in ['text', 'all']:
        # Text report is generated by default
        text_file = harness.reporter.output_path / f"report_{report.execution_id}.txt"
        if text_file.exists():
            generated_files.append(text_file)
    
    if output_format in ['json', 'all']:
        # JSON report is generated by default
        json_file = harness.reporter.output_path / f"report_{report.execution_id}.json"
        if json_file.exists():
            generated_files.append(json_file)
    
    if output_format in ['junit', 'all']:
        # Generate JUnit XML report
        junit_file = harness.reporter.save_ci_report(report, "junit")
        generated_files.append(junit_file)
    
    # Generate CI JSON report for CI mode
    if harness.config.mode == HarnessMode.CI:
        ci_json_file = harness.reporter.save_ci_report(report, "json")
        generated_files.append(ci_json_file)
    
    return generated_files


def print_summary(report, generated_files: List[Path]) -> None:
    """Print execution summary."""
    print("\n" + "=" * 60)
    print("CLI Workflow Harness - Execution Summary")
    print("=" * 60)
    print(f"Execution ID: {report.execution_id}")
    print(f"Mode: {report.mode}")
    print(f"Duration: {report.performance_metrics.total_duration:.2f}s")
    print(f"Total Tests: {report.total_tests}")
    print(f"Passed: {report.passed_tests}")
    print(f"Failed: {report.failed_tests}")
    print(f"Success Rate: {report.success_rate:.1f}%")
    
    if report.performance_metrics.peak_memory_mb > 0:
        print(f"Peak Memory: {report.performance_metrics.peak_memory_mb:.1f} MB")
    
    if hasattr(report.performance_metrics, 'parallel_efficiency'):
        print(f"Parallel Efficiency: {report.performance_metrics.parallel_efficiency:.1f}%")
    
    # Show critical issues
    critical_features = [f for f in report.missing_features if f.impact == "critical"]
    if critical_features:
        print(f"\nCritical Issues: {len(critical_features)}")
        for feature in critical_features[:3]:  # Show top 3
            print(f"  - {feature.feature_name} ({feature.component})")
    
    # Show top recommendations
    if report.recommendations:
        print(f"\nTop Recommendations:")
        for rec in report.recommendations[:3]:  # Show top 3
            print(f"  {rec.priority}. [{rec.category.upper()}] {rec.description}")
    
    # Show generated files
    print(f"\nGenerated Reports:")
    for file_path in generated_files:
        print(f"  - {file_path}")
    
    print("=" * 60)


def main() -> int:
    """Main entry point."""
    args = parse_arguments()
    
    # Set up logging
    setup_logging(args.verbose, args.log_file)
    logger = logging.getLogger(__name__)
    
    try:
        # Create output directory
        args.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create harness configuration
        config = create_harness_config(args)
        
        logger.info(f"Starting CLI Workflow Harness in {config.mode.value} mode")
        logger.info(f"Components: {config.components or 'all'}")
        logger.info(f"Output directory: {config.output_path}")
        
        # Create and run harness
        harness = CLIWorkflowHarness(config)
        report = harness.run()
        
        # Generate output reports
        generated_files = generate_output_reports(harness, report, args.output_format)
        
        # Print summary
        if not args.ci or args.verbose:
            print_summary(report, generated_files)
        
        # Determine exit code
        exit_code = 0
        if args.exit_on_failure or config.mode == HarnessMode.CI:
            # Use CI exit code logic
            exit_code = harness.get_ci_exit_code()
            if exit_code != 0:
                logger.error(f"Harness execution failed with exit code {exit_code}")
        
        logger.info(f"Harness execution completed with exit code {exit_code}")
        return exit_code
        
    except KeyboardInterrupt:
        logger.info("Harness execution interrupted by user")
        return 130  # Standard exit code for SIGINT
        
    except Exception as e:
        logger.error(f"Harness execution failed: {e}")
        if args.verbose:
            import traceback
            logger.error(traceback.format_exc())
        return 1


if __name__ == '__main__':
    sys.exit(main())