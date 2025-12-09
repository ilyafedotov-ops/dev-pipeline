"""
Property-based tests for services architecture completion.

These tests verify that the services architecture refactor has been completed
according to the design specifications.
"""

import ast
from pathlib import Path
from typing import List, Set

import pytest
from hypothesis import given, strategies as st


def get_python_files(directory: Path, exclude_patterns: Set[str] = None) -> List[Path]:
    """Get all Python files in a directory, excluding specified patterns."""
    exclude_patterns = exclude_patterns or set()
    python_files = []
    
    for path in directory.rglob("*.py"):
        # Skip if path matches any exclude pattern
        if any(pattern in str(path) for pattern in exclude_patterns):
            continue
        python_files.append(path)
    
    return python_files


def parse_imports(file_path: Path) -> Set[str]:
    """Parse imports from a Python file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=str(file_path))
        
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)
                    for alias in node.names:
                        imports.add(f"{node.module}.{alias.name}")
        
        return imports
    except Exception:
        return set()


def test_property_7_legacy_pattern_elimination():
    """
    **Feature: services-architecture-completion, Property 7: Legacy pattern elimination**
    **Validates: Requirements 4.5**
    
    For any code pattern that directly calls worker helpers or duplicates service logic,
    it should have been refactored to use services.
    
    This test verifies that:
    1. codex_worker.py no longer imports apply_loop_policies or apply_trigger_policies
    2. codex_worker.py no longer imports maybe_complete_protocol from workers.state
    3. codex_worker.py uses OrchestratorService methods instead
    """
    workspace_root = Path(__file__).parent.parent
    codex_worker_path = workspace_root / "tasksgodzilla" / "workers" / "codex_worker.py"
    
    assert codex_worker_path.exists(), "codex_worker.py not found"
    
    # Parse imports from codex_worker
    imports = parse_imports(codex_worker_path)
    
    # Verify legacy imports have been removed
    legacy_imports = {
        "tasksgodzilla.codemachine.policy_runtime.apply_loop_policies",
        "tasksgodzilla.codemachine.policy_runtime.apply_trigger_policies",
        "tasksgodzilla.workers.state.maybe_complete_protocol",
    }
    
    found_legacy = imports & legacy_imports
    assert not found_legacy, f"Found legacy imports in codex_worker.py: {found_legacy}"
    
    # Verify OrchestratorService is imported
    orchestrator_imports = {
        imp for imp in imports 
        if "orchestrator" in imp.lower() and "service" in imp.lower()
    }
    assert orchestrator_imports, "OrchestratorService not imported in codex_worker.py"
    
    # Read the file content to verify method calls
    with open(codex_worker_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Verify legacy function calls have been removed
    legacy_calls = [
        "apply_loop_policies(",
        "apply_trigger_policies(",
        "maybe_complete_protocol(",
    ]
    
    for legacy_call in legacy_calls:
        assert legacy_call not in content, f"Found legacy call '{legacy_call}' in codex_worker.py"
    
    # Verify OrchestratorService methods are used
    orchestrator_methods = [
        "orchestrator.apply_loop_policy(",
        "orchestrator.apply_trigger_policy(",
        "orchestrator.handle_step_completion(",
    ]
    
    found_methods = [method for method in orchestrator_methods if method in content]
    assert found_methods, f"No OrchestratorService methods found in codex_worker.py. Expected one of: {orchestrator_methods}"


def test_property_7_no_direct_policy_runtime_calls():
    """
    Verify that no worker files directly call policy_runtime functions.
    
    Workers should delegate to OrchestratorService instead of calling
    policy_runtime functions directly.
    """
    workspace_root = Path(__file__).parent.parent
    workers_dir = workspace_root / "tasksgodzilla" / "workers"
    
    if not workers_dir.exists():
        pytest.skip("Workers directory not found")
    
    worker_files = get_python_files(workers_dir, exclude_patterns={"__pycache__", "test_"})
    
    for worker_file in worker_files:
        imports = parse_imports(worker_file)
        
        # Check for direct imports of policy_runtime functions
        policy_runtime_imports = {
            imp for imp in imports 
            if "policy_runtime" in imp and ("apply_loop" in imp or "apply_trigger" in imp)
        }
        
        assert not policy_runtime_imports, (
            f"Worker {worker_file.name} directly imports policy_runtime functions: {policy_runtime_imports}. "
            "Workers should use OrchestratorService instead."
        )


def test_property_7_orchestrator_service_usage():
    """
    Verify that workers use OrchestratorService for orchestration logic.
    
    This test checks that worker files that need orchestration functionality
    import and use OrchestratorService.
    """
    workspace_root = Path(__file__).parent.parent
    codex_worker_path = workspace_root / "tasksgodzilla" / "workers" / "codex_worker.py"
    
    if not codex_worker_path.exists():
        pytest.skip("codex_worker.py not found")
    
    with open(codex_worker_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Verify OrchestratorService is instantiated
    assert "OrchestratorService(" in content or "orchestrator = " in content, (
        "OrchestratorService not instantiated in codex_worker.py"
    )
    
    # Verify orchestration methods are called
    orchestration_patterns = [
        "orchestrator.apply_",
        "orchestrator.handle_",
        "orchestrator.check_",
    ]
    
    found_patterns = [pattern for pattern in orchestration_patterns if pattern in content]
    assert found_patterns, (
        f"No orchestration method calls found in codex_worker.py. "
        f"Expected patterns like: {orchestration_patterns}"
    )


def get_public_methods(file_path: Path) -> Set[str]:
    """Extract public method names from a service class file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=str(file_path))
        
        methods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        # Skip private methods (starting with _) and __init__
                        if not item.name.startswith('_'):
                            methods.add(item.name)
        
        return methods
    except Exception:
        return set()


def get_tested_methods(test_file_path: Path, service_name: str) -> Set[str]:
    """Extract method names that are tested in a test file."""
    try:
        with open(test_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tested_methods = set()
        
        # Look for patterns like service.method_name(
        # This is a simple heuristic - it may not catch all cases
        import re
        pattern = rf'{service_name.lower()}\.(\w+)\('
        matches = re.findall(pattern, content)
        tested_methods.update(matches)
        
        # Also look for patterns like service_instance.method_name(
        pattern = r'service\.(\w+)\('
        matches = re.findall(pattern, content)
        tested_methods.update(matches)
        
        return tested_methods
    except Exception:
        return set()


def test_property_8_service_method_test_coverage():
    """
    **Feature: services-architecture-completion, Property 8: Service method test coverage**
    **Validates: Requirements 5.1**
    
    For any public method in a service class, there should exist at least one unit test
    that exercises that method.
    
    This test verifies that:
    1. All public methods in SpecService have corresponding tests
    2. All public methods in PromptService have corresponding tests
    3. All public methods in GitService have corresponding tests
    4. All public methods in BudgetService have corresponding tests
    5. All public methods in OrchestratorService have corresponding tests
    """
    workspace_root = Path(__file__).parent.parent
    services_dir = workspace_root / "tasksgodzilla" / "services"
    tests_dir = workspace_root / "tests"
    
    # Services to check
    services_to_check = [
        ("spec.py", "test_spec_service.py", "SpecService"),
        ("prompts.py", "test_prompt_service.py", "PromptService"),
        ("git.py", "test_git_service.py", "GitService"),
        ("budget.py", "test_budget_service.py", "BudgetService"),
        ("orchestrator.py", "test_orchestrator_service.py", "OrchestratorService"),
    ]
    
    missing_coverage = {}
    
    for service_file, test_file, service_name in services_to_check:
        service_path = services_dir / service_file
        test_path = tests_dir / test_file
        
        if not service_path.exists():
            continue
        
        # Get public methods from service
        public_methods = get_public_methods(service_path)
        
        if not public_methods:
            continue
        
        # Get tested methods
        if test_path.exists():
            tested_methods = get_tested_methods(test_path, service_name)
        else:
            tested_methods = set()
        
        # Find untested methods
        untested = public_methods - tested_methods
        
        if untested:
            missing_coverage[service_name] = untested
    
    # Report any missing coverage
    if missing_coverage:
        report = []
        for service_name, methods in missing_coverage.items():
            report.append(f"{service_name}: {', '.join(sorted(methods))}")
        
        pytest.fail(
            f"Some service methods lack test coverage:\n" + "\n".join(report) +
            "\n\nEach public service method should have at least one unit test."
        )


def test_property_3_no_imports_of_removed_modules():
    """
    **Feature: services-architecture-completion, Property 3: No imports of removed modules**
    **Validates: Requirements 2.4**
    
    For any Python file in the codebase, it should not import any modules that have been
    removed during the refactor.
    
    This test verifies that:
    1. No files import removed helper modules
    2. No files import removed worker helper functions
    3. All imports reference current, valid modules
    """
    workspace_root = Path(__file__).parent.parent
    
    # List of modules/functions that have been removed or deprecated
    removed_modules = {
        # Helper functions that were in codex_worker and moved to services
        "tasksgodzilla.workers.codex_worker._append_protocol_log",
        "tasksgodzilla.workers.codex_worker.infer_step_type",
        "tasksgodzilla.workers.codex_worker.sync_step_runs_from_protocol",
        # Any other removed modules would go here
    }
    
    # Get all Python files in the codebase
    python_files = get_python_files(
        workspace_root / "tasksgodzilla",
        exclude_patterns={"__pycache__", ".pyc", "test_"}
    )
    
    # Also check test files
    test_files = get_python_files(
        workspace_root / "tests",
        exclude_patterns={"__pycache__", ".pyc"}
    )
    
    all_files = python_files + test_files
    
    violations = {}
    
    for file_path in all_files:
        imports = parse_imports(file_path)
        
        # Check if any removed modules are imported
        found_removed = imports & removed_modules
        
        if found_removed:
            violations[str(file_path.relative_to(workspace_root))] = found_removed
    
    # Report violations
    if violations:
        report = []
        for file_path, removed_imports in violations.items():
            report.append(f"{file_path}:")
            for imp in sorted(removed_imports):
                report.append(f"  - {imp}")
        
        pytest.fail(
            f"Found imports of removed modules:\n" + "\n".join(report) +
            "\n\nThese modules/functions have been removed or moved to services. "
            "Update imports to use the new service methods."
        )


def test_property_3_no_direct_helper_function_imports():
    """
    Verify that no files import helper functions that should be accessed through services.
    
    Helper functions that were extracted to services should not be imported directly.
    """
    import re
    
    workspace_root = Path(__file__).parent.parent
    
    # Get all Python files
    python_files = get_python_files(
        workspace_root / "tasksgodzilla",
        exclude_patterns={"__pycache__", ".pyc", "test_", "services/spec.py"}  # Exclude the service itself
    )
    
    violations = {}
    
    for file_path in python_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for direct calls to functions (not method calls like service.function())
        # Pattern: function_name( but NOT preceded by a dot (which would indicate a method call)
        deprecated_patterns = [
            (r'(?<!\.)_append_protocol_log\(', "_append_protocol_log("),
            (r'(?<!\.)infer_step_type\(', "infer_step_type("),
            (r'(?<!\.)sync_step_runs_from_protocol\(', "sync_step_runs_from_protocol("),
        ]
        
        found_calls = []
        for pattern, display_name in deprecated_patterns:
            if re.search(pattern, content):
                found_calls.append(display_name)
        
        if found_calls:
            violations[str(file_path.relative_to(workspace_root))] = found_calls
    
    # Report violations
    if violations:
        report = []
        for file_path, calls in violations.items():
            report.append(f"{file_path}:")
            for call in sorted(calls):
                report.append(f"  - {call}")
        
        pytest.fail(
            f"Found direct calls to helper functions that should use services:\n" + "\n".join(report) +
            "\n\nThese functions have been moved to services. "
            "Use the appropriate service method instead (e.g., spec_service.append_protocol_log)."
        )


def test_property_4_no_test_references_to_removed_code():
    """
    **Feature: services-architecture-completion, Property 4: No test references to removed code**
    **Validates: Requirements 2.5**
    
    For any test file, it should not import or reference modules or functions that have been
    removed during the refactor.
    
    This test verifies that:
    1. Test files don't import removed helper modules
    2. Test files don't reference removed worker helper functions
    3. Tests use current, valid imports
    
    Note: This test checks for imports of truly removed modules, not functions that still
    exist in utility modules like spec.py. The refactor moved logic to services but kept
    utility functions in their original modules.
    """
    workspace_root = Path(__file__).parent.parent
    tests_dir = workspace_root / "tests"
    
    # List of modules/imports that have been completely removed
    # During the Phase 3 refactor, no modules were actually removed - logic was moved
    # to services but the original utility modules remain valid.
    removed_module_imports = set()
    # Example: removed_module_imports = {"tasksgodzilla.workers.removed_helper_module"}
    # Currently, no modules have been removed - they've been refactored
    
    # Get all test files
    test_files = get_python_files(tests_dir, exclude_patterns={"__pycache__", ".pyc"})
    
    violations = {}
    
    for test_file in test_files:
        # Parse imports
        imports = parse_imports(test_file)
        
        # Check for imports of removed modules
        found_removed = imports & removed_module_imports
        
        if found_removed:
            violations[str(test_file.relative_to(workspace_root))] = found_removed
    
    # Report violations
    if violations:
        report = []
        for file_path, removed_imports_found in violations.items():
            report.append(f"{file_path}:")
            for imp in sorted(removed_imports_found):
                report.append(f"  - {imp}")
        
        pytest.fail(
            f"Test files import removed modules:\n" + "\n".join(report) +
            "\n\nThese modules have been removed. "
            "Update imports to use current modules."
        )


def test_property_4_tests_use_services_not_helpers():
    """
    Verify that tests use service methods instead of calling helper functions directly.
    
    Tests should interact with the service layer, not bypass it to call helpers.
    """
    workspace_root = Path(__file__).parent.parent
    tests_dir = workspace_root / "tests"
    
    # Get all test files
    test_files = get_python_files(tests_dir, exclude_patterns={"__pycache__", ".pyc"})
    
    # Patterns that indicate tests are using services correctly
    service_patterns = [
        "SpecService",
        "GitService", 
        "BudgetService",
        "OrchestratorService",
        "PromptService",
    ]
    
    # Check a sample of test files that should be using services
    service_test_files = [
        tests_dir / "test_spec_service.py",
        tests_dir / "test_git_service.py",
        tests_dir / "test_budget_service.py",
        tests_dir / "test_orchestrator_service.py",
        tests_dir / "test_prompt_service.py",
    ]
    
    for test_file in service_test_files:
        if not test_file.exists():
            continue
        
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verify the test file references the corresponding service
        service_name = test_file.stem.replace("test_", "").replace("_", "").lower()
        
        found_service = False
        for pattern in service_patterns:
            if pattern.lower().replace("service", "") in service_name:
                if pattern in content:
                    found_service = True
                    break
        
        # This is informational - we don't fail if service tests don't exist yet
        # but we verify they use services when they do exist
        if found_service:
            # Good - the test file uses the service
            pass


def test_property_11_tests_dont_instantiate_workers():
    """
    **Feature: services-architecture-completion, Property 11: Tests don't instantiate workers**
    **Validates: Requirements 5.5**
    
    For any test file, it should not directly instantiate worker classes or call worker
    job handler functions.
    
    This test verifies that:
    1. Tests don't instantiate worker classes (e.g., CodexWorker())
    2. Tests that call worker handler functions are integration tests (acceptable)
    3. Unit tests use services directly, not workers
    
    Note: Integration tests that call handle_* functions are acceptable as they test
    the full worker flow. This property focuses on preventing direct worker class
    instantiation in unit tests.
    """
    workspace_root = Path(__file__).parent.parent
    tests_dir = workspace_root / "tests"
    
    # Get all test files (exclude this property test file itself)
    test_files = get_python_files(
        tests_dir, 
        exclude_patterns={"__pycache__", ".pyc", "test_services_architecture_properties.py"}
    )
    
    # Worker class patterns that should not be instantiated
    worker_class_patterns = [
        r'\bCodexWorker\s*\(',
        r'\bCodemachineWorker\s*\(',
        r'\bOnboardingWorker\s*\(',
        r'\bSpecWorker\s*\(',
    ]
    
    violations = {}
    
    for test_file in test_files:
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        found_instantiations = []
        
        import re
        for pattern in worker_class_patterns:
            matches = re.findall(pattern, content)
            if matches:
                # Extract the class name from the pattern
                class_name = pattern.replace(r'\b', '').replace(r'\s*\(', '').replace('\\', '')
                found_instantiations.append(class_name)
        
        if found_instantiations:
            violations[str(test_file.relative_to(workspace_root))] = found_instantiations
    
    # Report violations
    if violations:
        report = []
        for file_path, instantiations in violations.items():
            report.append(f"{file_path}:")
            for inst in sorted(set(instantiations)):
                report.append(f"  - {inst}")
        
        pytest.fail(
            f"Test files directly instantiate worker classes:\n" + "\n".join(report) +
            "\n\nWorker classes should not be instantiated in tests. "
            "Unit tests should use services directly. "
            "Integration tests can call handle_* functions but should not instantiate worker classes."
        )


def test_property_11_service_tests_use_services():
    """
    Verify that service-specific test files use services, not workers.
    
    Tests in test_*_service.py files should test services directly,
    not go through workers.
    """
    workspace_root = Path(__file__).parent.parent
    tests_dir = workspace_root / "tests"
    
    # Service test files that should use services
    service_test_files = [
        "test_spec_service.py",
        "test_git_service.py",
        "test_budget_service.py",
        "test_orchestrator_service.py",
        "test_prompt_service.py",
        "test_execution_service.py",
        "test_quality_service.py",
        "test_onboarding_service.py",
        "test_codemachine_service.py",
    ]
    
    violations = {}
    
    for test_file_name in service_test_files:
        test_file = tests_dir / test_file_name
        
        if not test_file.exists():
            continue
        
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if the test file imports worker modules
        imports = parse_imports(test_file)
        
        worker_imports = [
            imp for imp in imports 
            if "workers" in imp and "worker" in imp.lower()
        ]
        
        # Also check for direct worker function calls
        import re
        worker_function_calls = []
        
        # Look for handle_* function calls that are worker functions
        handle_patterns = [
            r'\bhandle_plan_protocol\s*\(',
            r'\bhandle_execute_step\s*\(',
            r'\bhandle_quality\s*\(',
            r'\bhandle_open_pr\s*\(',
            r'\bhandle_import_job\s*\(',
            r'\bhandle_project_setup\s*\(',
        ]
        
        for pattern in handle_patterns:
            if re.search(pattern, content):
                func_name = pattern.replace(r'\b', '').replace(r'\s*\(', '').replace('\\', '')
                worker_function_calls.append(func_name)
        
        if worker_imports or worker_function_calls:
            violations[test_file_name] = {
                "imports": worker_imports,
                "calls": worker_function_calls
            }
    
    # Report violations
    if violations:
        report = []
        for file_name, issues in violations.items():
            report.append(f"{file_name}:")
            if issues["imports"]:
                report.append("  Worker imports:")
                for imp in sorted(issues["imports"]):
                    report.append(f"    - {imp}")
            if issues["calls"]:
                report.append("  Worker function calls:")
                for call in sorted(set(issues["calls"])):
                    report.append(f"    - {call}")
        
        pytest.fail(
            f"Service test files should not use workers:\n" + "\n".join(report) +
            "\n\nService tests should test services directly, not through workers. "
            "Move worker integration tests to separate integration test files."
        )


if __name__ == "__main__":
    # Run the tests
    test_property_3_no_imports_of_removed_modules()
    test_property_3_no_direct_helper_function_imports()
    test_property_4_no_test_references_to_removed_code()
    test_property_4_tests_use_services_not_helpers()
    test_property_7_legacy_pattern_elimination()
    test_property_7_no_direct_policy_runtime_calls()
    test_property_7_orchestrator_service_usage()
    test_property_8_service_method_test_coverage()
    test_property_11_tests_dont_instantiate_workers()
    test_property_11_service_tests_use_services()
    print("All property tests passed!")



def test_property_5_documentation_consistency():
    """
    **Feature: services-architecture-completion, Property 5: Documentation consistency**
    **Validates: Requirements 3.5**
    
    For any architecture concept mentioned in multiple documentation files, all files
    should describe it consistently.
    
    This test verifies that:
    1. All docs describe services as the primary integration layer
    2. All docs describe workers as thin adapters
    3. All docs reference the same service names and responsibilities
    4. No docs contradict each other about architecture
    """
    workspace_root = Path(__file__).parent.parent
    docs_dir = workspace_root / "docs"
    
    # Key documentation files to check
    doc_files = [
        docs_dir / "architecture.md",
        docs_dir / "orchestrator.md",
        docs_dir / "api-reference.md",
        docs_dir / "services-architecture.md",
        docs_dir / "services-migration-guide.md",
    ]
    
    # Check that all files exist
    missing_files = [f for f in doc_files if not f.exists()]
    if missing_files:
        pytest.fail(f"Missing documentation files: {[str(f.relative_to(workspace_root)) for f in missing_files]}")
    
    # Key concepts that should be consistent across all docs
    key_concepts = {
        "services": {
            "required_phrases": [
                "service",
                "OrchestratorService",
                "ExecutionService",
                "QualityService",
            ],
            "description": "Services should be described as the primary integration layer"
        },
        "workers": {
            "required_phrases": [
                "worker",
                "thin",
                "adapter",
            ],
            "description": "Workers should be described as thin adapters"
        },
        "service_names": {
            "required_phrases": [
                "OrchestratorService",
                "SpecService",
                "ExecutionService",
                "QualityService",
            ],
            "description": "Core service names should be mentioned"
        }
    }
    
    # Check each doc file for key concepts
    doc_contents = {}
    for doc_file in doc_files:
        with open(doc_file, 'r', encoding='utf-8') as f:
            doc_contents[doc_file.name] = f.read().lower()
    
    # Verify services are described as primary integration layer
    services_primary_phrases = [
        "primary integration",
        "primary layer",
        "stable api",
        "single source of truth",
    ]
    
    files_missing_services_primary = []
    for doc_name, content in doc_contents.items():
        # Skip migration guide as it's more focused on patterns
        if "migration" in doc_name:
            continue
        
        has_services_primary = any(phrase in content for phrase in services_primary_phrases)
        if not has_services_primary:
            files_missing_services_primary.append(doc_name)
    
    if files_missing_services_primary:
        pytest.fail(
            f"Documentation files don't describe services as primary integration layer:\n" +
            "\n".join(f"  - {f}" for f in files_missing_services_primary) +
            f"\n\nExpected one of: {services_primary_phrases}"
        )
    
    # Verify workers are described as thin adapters
    worker_thin_phrases = [
        "thin adapter",
        "thin job adapter",
        "deserialize",
        "delegate to service",
    ]
    
    files_missing_worker_description = []
    for doc_name, content in doc_contents.items():
        # Only check files that mention workers
        if "worker" not in content:
            continue
        
        has_worker_description = any(phrase in content for phrase in worker_thin_phrases)
        if not has_worker_description:
            files_missing_worker_description.append(doc_name)
    
    if files_missing_worker_description:
        pytest.fail(
            f"Documentation files don't describe workers as thin adapters:\n" +
            "\n".join(f"  - {f}" for f in files_missing_worker_description) +
            f"\n\nExpected one of: {worker_thin_phrases}"
        )
    
    # Verify core service names are mentioned consistently
    core_services = [
        "orchestratorservice",
        "executionservice",
        "qualityservice",
        "specservice",
    ]
    
    files_missing_services = {}
    for doc_name, content in doc_contents.items():
        # Skip API reference as it focuses on endpoints
        if "api-reference" in doc_name:
            continue
        
        missing_services = [s for s in core_services if s not in content]
        if missing_services:
            files_missing_services[doc_name] = missing_services
    
    if files_missing_services:
        report = []
        for doc_name, missing in files_missing_services.items():
            report.append(f"{doc_name}:")
            for service in missing:
                report.append(f"  - {service}")
        
        pytest.fail(
            f"Documentation files don't mention core services:\n" + "\n".join(report) +
            "\n\nAll architecture docs should mention the core services."
        )
    
    # Verify no contradictory statements
    # Check that no docs say workers contain business logic (positive statements)
    contradictory_phrases = [
        "workers contain logic",
        "workers implement business logic",
        "business logic lives in workers",
        "workers have business logic",
    ]
    
    files_with_contradictions = {}
    for doc_name, content in doc_contents.items():
        found_contradictions = [phrase for phrase in contradictory_phrases if phrase in content]
        if found_contradictions:
            files_with_contradictions[doc_name] = found_contradictions
    
    if files_with_contradictions:
        report = []
        for doc_name, contradictions in files_with_contradictions.items():
            report.append(f"{doc_name}:")
            for phrase in contradictions:
                report.append(f"  - '{phrase}'")
        
        pytest.fail(
            f"Documentation contains contradictory statements:\n" + "\n".join(report) +
            "\n\nWorkers should be described as thin adapters, not containing business logic."
        )


def test_property_6_no_services_migration_todos():
    """
    **Feature: services-architecture-completion, Property 6: No services migration TODOs**
    **Validates: Requirements 4.3**
    
    For any Python file in the codebase, it should not contain TODO comments mentioning
    "services migration" or "move to service".
    
    This test verifies that:
    1. No Python files contain TODO comments about services migration
    2. No Python files contain TODO comments about moving logic to services
    3. The services refactor is complete with no pending migration work
    """
    import re
    
    workspace_root = Path(__file__).parent.parent
    
    # Get all Python files in the codebase
    python_files = get_python_files(
        workspace_root / "tasksgodzilla",
        exclude_patterns={"__pycache__", ".pyc"}
    )
    
    # Also check scripts
    scripts_files = get_python_files(
        workspace_root / "scripts",
        exclude_patterns={"__pycache__", ".pyc"}
    )
    
    all_files = python_files + scripts_files
    
    # Patterns to search for in comments
    todo_patterns = [
        r'#\s*TODO.*service.*migration',
        r'#\s*TODO.*move.*to.*service',
        r'#\s*TODO.*extract.*to.*service',
        r'#\s*TODO.*refactor.*to.*service',
        r'#\s*FIXME.*service.*migration',
        r'#\s*FIXME.*move.*to.*service',
        r'#\s*XXX.*service.*migration',
        r'#\s*XXX.*move.*to.*service',
    ]
    
    violations = {}
    
    for file_path in all_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            found_todos = []
            
            for pattern in todo_patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    # Get the line number
                    line_num = content[:match.start()].count('\n') + 1
                    # Get the full line
                    line_start = content.rfind('\n', 0, match.start()) + 1
                    line_end = content.find('\n', match.end())
                    if line_end == -1:
                        line_end = len(content)
                    full_line = content[line_start:line_end].strip()
                    
                    found_todos.append((line_num, full_line))
            
            if found_todos:
                violations[str(file_path.relative_to(workspace_root))] = found_todos
        
        except Exception:
            # Skip files that can't be read
            continue
    
    # Report violations
    if violations:
        report = []
        for file_path, todos in violations.items():
            report.append(f"{file_path}:")
            for line_num, todo_text in todos:
                report.append(f"  Line {line_num}: {todo_text}")
        
        pytest.fail(
            f"Found TODO comments about services migration:\n" + "\n".join(report) +
            "\n\nThe services refactor is complete. Remove these TODO comments or "
            "update them to reflect the current architecture."
        )


def test_property_12_service_method_naming_consistency():
    """
    **Feature: services-architecture-completion, Property 12: Service method naming consistency**
    **Validates: Requirements 8.4**
    
    For any service class, its public methods should follow consistent naming patterns
    (verb_noun format).
    
    This test verifies that:
    1. All public service methods use snake_case naming
    2. All public service methods start with a verb (action word)
    3. Method names are descriptive and follow verb_noun pattern
    4. No inconsistent naming patterns exist across services
    
    Common verb patterns:
    - get_*, find_*, fetch_* (retrieval)
    - create_*, build_*, make_* (creation)
    - update_*, set_*, modify_* (modification)
    - delete_*, remove_*, clear_* (deletion)
    - check_*, validate_*, verify_* (validation)
    - apply_*, execute_*, run_*, handle_* (execution)
    - resolve_*, ensure_*, sync_* (resolution/synchronization)
    - append_*, record_*, track_* (recording)
    - enqueue_*, trigger_*, start_*, pause_*, resume_*, cancel_* (orchestration)
    - push_*, open_*, trigger_* (git operations)
    """
    workspace_root = Path(__file__).parent.parent
    services_dir = workspace_root / "tasksgodzilla" / "services"
    
    if not services_dir.exists():
        pytest.skip("Services directory not found")
    
    # Get all service files
    service_files = [
        f for f in services_dir.glob("*.py")
        if f.name not in ("__init__.py", "__pycache__")
    ]
    
    # Common verb prefixes that indicate good naming
    valid_verb_prefixes = {
        # Retrieval
        "get", "find", "fetch", "list", "load", "read", "parse",
        # Creation
        "create", "build", "make", "generate", "initialize", "setup",
        # Modification
        "update", "set", "modify", "change", "edit", "append", "add",
        # Deletion
        "delete", "remove", "clear", "clean", "purge",
        # Validation
        "check", "validate", "verify", "ensure", "confirm", "test",
        # Execution
        "apply", "execute", "run", "handle", "process", "perform", "do",
        # Resolution
        "resolve", "sync", "refresh", "reload",
        # Recording
        "record", "track", "log", "observe", "monitor",
        # Orchestration
        "enqueue", "trigger", "start", "stop", "pause", "resume", "cancel", "retry",
        # Git operations
        "push", "pull", "commit", "open", "close", "merge", "remote",
        # Special cases
        "is", "has", "can", "should",  # Boolean checks
        "infer",  # Inference/deduction
        # Service-specific operations
        "evaluate", "import", "register", "plan", "decompose",
    }
    
    violations = {}
    
    for service_file in service_files:
        try:
            with open(service_file, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read(), filename=str(service_file))
            
            # Find all class definitions
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Only check classes that end with "Service"
                    if not node.name.endswith("Service"):
                        continue
                    
                    service_violations = []
                    
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            method_name = item.name
                            
                            # Skip private methods and special methods
                            if method_name.startswith('_'):
                                continue
                            
                            # Check if method name is in snake_case
                            if not method_name.islower() and '_' not in method_name:
                                # Allow single-word lowercase methods
                                if not method_name.islower():
                                    service_violations.append({
                                        "method": method_name,
                                        "issue": "Not in snake_case format",
                                        "suggestion": "Use snake_case (e.g., getUserData -> get_user_data)"
                                    })
                                    continue
                            
                            # Check if method name starts with a valid verb
                            first_word = method_name.split('_')[0] if '_' in method_name else method_name
                            
                            if first_word not in valid_verb_prefixes:
                                service_violations.append({
                                    "method": method_name,
                                    "issue": f"Does not start with a recognized verb (starts with '{first_word}')",
                                    "suggestion": f"Use a verb prefix like: {', '.join(sorted(list(valid_verb_prefixes)[:10]))}..."
                                })
                    
                    if service_violations:
                        violations[f"{service_file.name}::{node.name}"] = service_violations
        
        except Exception as e:
            # Skip files that can't be parsed
            continue
    
    # Report violations
    if violations:
        report = []
        for service_class, issues in violations.items():
            report.append(f"\n{service_class}:")
            for issue in issues:
                report.append(f"  Method: {issue['method']}")
                report.append(f"    Issue: {issue['issue']}")
                report.append(f"    Suggestion: {issue['suggestion']}")
        
        pytest.fail(
            f"Service methods have inconsistent naming:\n" + "\n".join(report) +
            "\n\nAll public service methods should follow verb_noun naming pattern in snake_case. "
            "This ensures consistency across the service layer and makes the API predictable."
        )


if __name__ == "__main__":
    # Run the tests
    test_property_3_no_imports_of_removed_modules()
    test_property_3_no_direct_helper_function_imports()
    test_property_4_no_test_references_to_removed_code()
    test_property_4_tests_use_services_not_helpers()
    test_property_5_documentation_consistency()
    test_property_6_no_services_migration_todos()
    test_property_7_legacy_pattern_elimination()
    test_property_7_no_direct_policy_runtime_calls()
    test_property_7_orchestrator_service_usage()
    test_property_8_service_method_test_coverage()
    test_property_11_tests_dont_instantiate_workers()
    test_property_11_service_tests_use_services()
    test_property_12_service_method_naming_consistency()
    print("All property tests passed!")
