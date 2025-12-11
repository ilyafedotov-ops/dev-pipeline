"""Test data generator for creating realistic test projects."""

import json
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
import tempfile
import shutil

from .config import HarnessProject
from .models import HarnessStatus


class TestDataGenerator:
    """Generates realistic test projects for harness validation."""
    
    def __init__(self, base_temp_dir: Path):
        self.base_temp_dir = base_temp_dir
        self.base_temp_dir.mkdir(parents=True, exist_ok=True)
    
    def create_python_project(self, name: str = "test-python-project") -> HarnessProject:
        """Create a realistic Python project with tests, docs, and CI."""
        project_dir = self.base_temp_dir / name
        project_dir.mkdir(parents=True, exist_ok=True)
        
        # Create directory structure
        (project_dir / "src").mkdir(exist_ok=True)
        (project_dir / "tests").mkdir(exist_ok=True)
        (project_dir / "docs").mkdir(exist_ok=True)
        (project_dir / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
        
        # Create setup.py
        self._create_python_setup(project_dir, name)
        
        # Create main package
        self._create_python_package(project_dir, name)
        
        # Create comprehensive tests
        self._create_python_tests(project_dir, name.replace("-", "_"))
        
        # Create documentation
        self._create_python_docs(project_dir, name)
        
        # Create CI configuration
        self._create_python_ci(project_dir, name)
        
        # Initialize Git repository with realistic history
        self._initialize_git_repo(project_dir, name, "python")
        
        return HarnessProject(
            name=name,
            git_url="",
            local_path=project_dir,
            project_type="python",
            has_tests=True,
            has_docs=True,
            has_ci=True,
        )
    
    def create_javascript_project(self, name: str = "test-js-project") -> HarnessProject:
        """Create a realistic JavaScript project with package.json and tests."""
        project_dir = self.base_temp_dir / name
        project_dir.mkdir(parents=True, exist_ok=True)
        
        # Create directory structure
        (project_dir / "src").mkdir(exist_ok=True)
        (project_dir / "test").mkdir(exist_ok=True)
        (project_dir / "docs").mkdir(exist_ok=True)
        (project_dir / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
        
        # Create package.json
        self._create_javascript_package_json(project_dir, name)
        
        # Create main application files
        self._create_javascript_src(project_dir, name)
        
        # Create tests
        self._create_javascript_tests(project_dir, name)
        
        # Create configuration files
        self._create_javascript_config(project_dir)
        
        # Create documentation
        self._create_javascript_docs(project_dir, name)
        
        # Create CI configuration
        self._create_javascript_ci(project_dir, name)
        
        # Initialize Git repository
        self._initialize_git_repo(project_dir, name, "javascript")
        
        return HarnessProject(
            name=name,
            git_url="",
            local_path=project_dir,
            project_type="javascript",
            has_tests=True,
            has_docs=True,
            has_ci=True,
        )
    
    def create_mixed_project(self, name: str = "test-mixed-project") -> HarnessProject:
        """Create a mixed-language project with both Python and JavaScript components."""
        project_dir = self.base_temp_dir / name
        project_dir.mkdir(parents=True, exist_ok=True)
        
        # Create directory structure
        (project_dir / "backend").mkdir(exist_ok=True)
        (project_dir / "frontend").mkdir(exist_ok=True)
        (project_dir / "shared").mkdir(exist_ok=True)
        (project_dir / "docs").mkdir(exist_ok=True)
        (project_dir / "tests").mkdir(exist_ok=True)
        (project_dir / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
        
        # Create Python backend
        self._create_mixed_python_backend(project_dir, name)
        
        # Create JavaScript frontend
        self._create_mixed_javascript_frontend(project_dir, name)
        
        # Create shared configuration
        self._create_mixed_shared_config(project_dir, name)
        
        # Create documentation
        self._create_mixed_docs(project_dir, name)
        
        # Create CI configuration
        self._create_mixed_ci(project_dir, name)
        
        # Initialize Git repository
        self._initialize_git_repo(project_dir, name, "mixed")
        
        return HarnessProject(
            name=name,
            git_url="",
            local_path=project_dir,
            project_type="mixed",
            has_tests=True,
            has_docs=True,
            has_ci=True,
        )
    
    def _create_python_setup(self, project_dir: Path, name: str) -> None:
        """Create setup.py and related files for Python project."""
        package_name = name.replace("-", "_")
        
        # Create setup.py
        setup_content = f'''"""Setup configuration for {name}."""
from setuptools import setup, find_packages

setup(
    name="{name}",
    version="0.1.0",
    description="A realistic Python test project",
    author="Test Author",
    author_email="test@example.com",
    packages=find_packages(where="src"),
    package_dir={{"": "src"}},
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.25.0",
        "click>=8.0.0",
    ],
    extras_require={{
        "dev": [
            "pytest>=6.0.0",
            "pytest-cov>=2.10.0",
            "black>=21.0.0",
            "flake8>=3.8.0",
            "mypy>=0.800",
            "hypothesis>=6.0.0",
        ],
    }},
    entry_points={{
        "console_scripts": [
            "{package_name}={package_name}.cli:main",
        ],
    }},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)'''
        (project_dir / "setup.py").write_text(setup_content)
        
        # Create pyproject.toml
        pyproject_content = f'''[build-system]
requires = ["setuptools>=45", "wheel"]
build-backend = "setuptools.build_meta"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "--strict-markers --disable-warnings"

[tool.black]
line-length = 88
target-version = ['py38']
include = '\\.pyi?$'

[tool.mypy]
python_version = "3.8"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.coverage.run]
source = ["src"]
omit = ["*/tests/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
]
'''
        (project_dir / "pyproject.toml").write_text(pyproject_content)
        
        # Create requirements files
        (project_dir / "requirements.txt").write_text("requests>=2.25.0\\nclick>=8.0.0\\n")
        (project_dir / "requirements-dev.txt").write_text("""pytest>=6.0.0
pytest-cov>=2.10.0
black>=21.0.0
flake8>=3.8.0
mypy>=0.800
hypothesis>=6.0.0
""")
    
    def _create_python_package(self, project_dir: Path, name: str) -> None:
        """Create main Python package with realistic modules."""
        package_name = name.replace("-", "_")
        package_dir = project_dir / "src" / package_name
        package_dir.mkdir(parents=True, exist_ok=True)
        
        # Create __init__.py
        (package_dir / "__init__.py").write_text(f'''"""
{name} - A realistic Python test project.
"""

__version__ = "0.1.0"
__author__ = "Test Author"
__email__ = "test@example.com"

from .core import Calculator, DataProcessor
from .utils import format_output, validate_input

__all__ = ["Calculator", "DataProcessor", "format_output", "validate_input"]
''')
        
        # Create core module with Calculator and DataProcessor classes
        self._create_python_core_module(package_dir, name)
        
        # Create utils module
        self._create_python_utils_module(package_dir, name)
        
        # Create CLI module
        self._create_python_cli_module(package_dir, name)
    
    def _create_python_core_module(self, package_dir: Path, name: str) -> None:
        """Create core.py module with Calculator and DataProcessor classes."""
        core_content = f'''"""Core functionality for {name}."""

from typing import List, Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)


class Calculator:
    """A simple calculator with basic operations."""
    
    def __init__(self):
        self.history: List[str] = []
    
    def add(self, a: float, b: float) -> float:
        """Add two numbers."""
        result = a + b
        self.history.append(f"{{a}} + {{b}} = {{result}}")
        logger.info(f"Addition: {{a}} + {{b}} = {{result}}")
        return result
    
    def subtract(self, a: float, b: float) -> float:
        """Subtract two numbers."""
        result = a - b
        self.history.append(f"{{a}} - {{b}} = {{result}}")
        logger.info(f"Subtraction: {{a}} - {{b}} = {{result}}")
        return result
    
    def multiply(self, a: float, b: float) -> float:
        """Multiply two numbers."""
        result = a * b
        self.history.append(f"{{a}} * {{b}} = {{result}}")
        logger.info(f"Multiplication: {{a}} * {{b}} = {{result}}")
        return result
    
    def divide(self, a: float, b: float) -> float:
        """Divide two numbers."""
        if b == 0:
            raise ValueError("Cannot divide by zero")
        result = a / b
        self.history.append(f"{{a}} / {{b}} = {{result}}")
        logger.info(f"Division: {{a}} / {{b}} = {{result}}")
        return result
    
    def get_history(self) -> List[str]:
        """Get calculation history."""
        return self.history.copy()
    
    def clear_history(self) -> None:
        """Clear calculation history."""
        self.history.clear()
        logger.info("History cleared")


class DataProcessor:
    """Process and analyze data."""
    
    def __init__(self):
        self.data: List[Dict[str, Any]] = []
    
    def load_data(self, data: List[Dict[str, Any]]) -> None:
        """Load data for processing."""
        self.data = data.copy()
        logger.info(f"Loaded {{len(self.data)}} records")
    
    def filter_data(self, key: str, value: Any) -> List[Dict[str, Any]]:
        """Filter data by key-value pair."""
        filtered = [item for item in self.data if item.get(key) == value]
        logger.info(f"Filtered {{len(filtered)}} records where {{key}}={{value}}")
        return filtered
    
    def aggregate_data(self, key: str) -> Dict[Any, int]:
        """Aggregate data by key."""
        aggregation = {{}}
        for item in self.data:
            value = item.get(key)
            if value is not None:
                aggregation[value] = aggregation.get(value, 0) + 1
        logger.info(f"Aggregated data by {{key}}: {{len(aggregation)}} unique values")
        return aggregation
    
    def export_data(self, filepath: str) -> None:
        """Export data to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.data, f, indent=2)
        logger.info(f"Exported {{len(self.data)}} records to {{filepath}}")
'''
        (package_dir / "core.py").write_text(core_content)
    
    def _create_python_utils_module(self, package_dir: Path, name: str) -> None:
        """Create utils.py module with utility functions."""
        utils_content = '''"""Utility functions."""

import re
from typing import Any, Dict, List, Optional


def format_output(data: Any, format_type: str = "json") -> str:
    """Format data for output."""
    if format_type == "json":
        import json
        return json.dumps(data, indent=2)
    elif format_type == "csv":
        if isinstance(data, list) and data and isinstance(data[0], dict):
            import csv
            import io
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
            return output.getvalue()
    return str(data)


def validate_input(data: Any, schema: Dict[str, Any]) -> bool:
    """Validate input data against a simple schema."""
    if not isinstance(data, dict):
        return False
    
    for key, expected_type in schema.items():
        if key not in data:
            return False
        
        if expected_type == "string" and not isinstance(data[key], str):
            return False
        elif expected_type == "number" and not isinstance(data[key], (int, float)):
            return False
        elif expected_type == "boolean" and not isinstance(data[key], bool):
            return False
        elif expected_type == "list" and not isinstance(data[key], list):
            return False
        elif expected_type == "dict" and not isinstance(data[key], dict):
            return False
    
    return True


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe filesystem usage."""
    sanitized = re.sub(r'[<>:"/\\\\|?*]', '_', filename)
    sanitized = sanitized.strip(' .')
    if len(sanitized) > 255:
        sanitized = sanitized[:255]
    return sanitized or "unnamed"
'''
        (package_dir / "utils.py").write_text(utils_content)
    
    def _create_python_cli_module(self, package_dir: Path, name: str) -> None:
        """Create cli.py module with Click-based CLI."""
        package_name = name.replace("-", "_")
        cli_content = f'''"""Command-line interface for {name}."""

import click
import json
import logging
from pathlib import Path
from typing import Optional

from .core import Calculator, DataProcessor
from .utils import format_output, validate_input


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def main(verbose: bool) -> None:
    """
    {name} - A realistic Python test project.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format='%(levelname)s: %(message)s')


@main.command()
@click.argument('operation', type=click.Choice(['add', 'subtract', 'multiply', 'divide']))
@click.argument('a', type=float)
@click.argument('b', type=float)
def calc(operation: str, a: float, b: float) -> None:
    """Perform calculator operations."""
    calculator = Calculator()
    
    try:
        if operation == 'add':
            result = calculator.add(a, b)
        elif operation == 'subtract':
            result = calculator.subtract(a, b)
        elif operation == 'multiply':
            result = calculator.multiply(a, b)
        elif operation == 'divide':
            result = calculator.divide(a, b)
        
        click.echo(f"Result: {{result}}")
        
    except ValueError as e:
        click.echo(f"Error: {{e}}", err=True)
        raise click.Abort()


@main.command()
def version() -> None:
    """Show version information."""
    from . import __version__, __author__
    click.echo(f"{name} version {{__version__}}")
    click.echo(f"Author: {{__author__}}")


if __name__ == '__main__':
    main()
'''
        (package_dir / "cli.py").write_text(cli_content)
    
    def _create_python_tests(self, project_dir: Path, package_name: str) -> None:
        """Create comprehensive Python tests."""
        tests_dir = project_dir / "tests"
        
        # Create conftest.py
        conftest_content = '''"""Test configuration and fixtures."""

import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Provide a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_data():
    """Provide sample data for testing."""
    return [
        {"id": 1, "name": "Alice", "age": 30, "city": "New York"},
        {"id": 2, "name": "Bob", "age": 25, "city": "San Francisco"},
        {"id": 3, "name": "Charlie", "age": 35, "city": "New York"},
    ]
'''
        (tests_dir / "conftest.py").write_text(conftest_content)
        
        # Create test for core module
        test_core_content = f'''"""Tests for core functionality."""

import pytest
from {package_name}.core import Calculator, DataProcessor


class TestCalculator:
    """Test Calculator class."""
    
    def test_add(self):
        """Test addition operation."""
        calc = Calculator()
        result = calc.add(2, 3)
        assert result == 5
        assert "2 + 3 = 5" in calc.get_history()
    
    def test_divide_by_zero(self):
        """Test division by zero raises error."""
        calc = Calculator()
        with pytest.raises(ValueError, match="Cannot divide by zero"):
            calc.divide(10, 0)


class TestDataProcessor:
    """Test DataProcessor class."""
    
    def test_load_data(self, sample_data):
        """Test data loading."""
        processor = DataProcessor()
        processor.load_data(sample_data)
        assert len(processor.data) == 3
    
    def test_filter_data(self, sample_data):
        """Test data filtering."""
        processor = DataProcessor()
        processor.load_data(sample_data)
        
        filtered = processor.filter_data("city", "New York")
        assert len(filtered) == 2
        assert all(item["city"] == "New York" for item in filtered)
'''
        (tests_dir / "test_core.py").write_text(test_core_content)
        
        # Create test for utils module
        test_utils_content = f'''"""Tests for utility functions."""

import pytest
from {package_name}.utils import format_output, validate_input, sanitize_filename


def test_format_json():
    """Test JSON formatting."""
    data = {{"name": "test", "value": 123}}
    result = format_output(data, "json")
    assert '"name": "test"' in result
    assert '"value": 123' in result


def test_validate_input():
    """Test input validation."""
    data = {{"name": "test", "count": 42}}
    schema = {{"name": "string", "count": "number"}}
    assert validate_input(data, schema) is True


def test_sanitize_filename():
    """Test filename sanitization."""
    result = sanitize_filename("valid_filename.txt")
    assert result == "valid_filename.txt"
'''
        (tests_dir / "test_utils.py").write_text(test_utils_content)
    
    def _create_python_docs(self, project_dir: Path, name: str) -> None:
        """Create documentation for Python project."""
        readme_content = f'''# {name}

A realistic Python test project for demonstrating CLI workflow harness capabilities.

## Features

- **Calculator**: Basic arithmetic operations with history tracking
- **Data Processor**: JSON data filtering, aggregation, and export
- **CLI Interface**: Command-line access to all functionality
- **Comprehensive Testing**: Unit tests with pytest
- **Type Hints**: Full type annotation support

## Installation

```bash
pip install -e .
```

## Usage

### Calculator

```bash
{name.replace('-', '_')} calc add 2 3
{name.replace('-', '_')} calc multiply 4 5
```

### Version

```bash
{name.replace('-', '_')} version
```

## Development

### Running Tests

```bash
pytest
```

### Code Quality

```bash
black src tests
flake8 src tests
mypy src
```

## License

MIT License
'''
        (project_dir / "README.md").write_text(readme_content)
    
    def _create_python_ci(self, project_dir: Path, name: str) -> None:
        """Create CI configuration for Python project."""
        workflows_dir = project_dir / ".github" / "workflows"
        
        ci_content = f'''name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.8, 3.9, "3.10", "3.11"]

    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python ${{{{ matrix.python-version }}}}
      uses: actions/setup-python@v4
      with:
        python-version: ${{{{ matrix.python-version }}}}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[dev]"
    
    - name: Test with pytest
      run: |
        pytest --cov={name.replace('-', '_')}
'''
        (workflows_dir / "ci.yml").write_text(ci_content)
    
    def _create_javascript_package_json(self, project_dir: Path, name: str) -> None:
        """Create package.json for JavaScript project."""
        package_json = {
            "name": name,
            "version": "1.0.0",
            "description": "A realistic JavaScript test project",
            "main": "src/index.js",
            "type": "module",
            "scripts": {
                "start": "node src/index.js",
                "test": "jest",
                "lint": "eslint src test"
            },
            "keywords": ["test", "javascript", "node", "example"],
            "author": "Test Author <test@example.com>",
            "license": "MIT",
            "dependencies": {
                "lodash": "^4.17.21"
            },
            "devDependencies": {
                "jest": "^29.5.0",
                "eslint": "^8.42.0"
            },
            "engines": {
                "node": ">=16.0.0"
            }
        }
        
        (project_dir / "package.json").write_text(json.dumps(package_json, indent=2))
    
    def _create_javascript_src(self, project_dir: Path, name: str) -> None:
        """Create JavaScript source files."""
        src_dir = project_dir / "src"
        
        # Create main index.js
        index_content = f'''/**
 * {name} - A realistic JavaScript test project
 */

import {{ Calculator }} from './calculator.js';

export {{ Calculator }};

// CLI entry point
if (import.meta.url === `file://${{process.argv[1]}}`) {{
    console.log('{name} - JavaScript test project');
}}
'''
        (src_dir / "index.js").write_text(index_content)
        
        # Create calculator module
        calculator_content = '''/**
 * Calculator class for basic arithmetic operations
 */

export class Calculator {
    constructor() {
        this.history = [];
    }

    add(a, b) {
        const result = a + b;
        this.history.push(`${a} + ${b} = ${result}`);
        return result;
    }

    subtract(a, b) {
        const result = a - b;
        this.history.push(`${a} - ${b} = ${result}`);
        return result;
    }

    multiply(a, b) {
        const result = a * b;
        this.history.push(`${a} * ${b} = ${result}`);
        return result;
    }

    divide(a, b) {
        if (b === 0) {
            throw new Error('Cannot divide by zero');
        }
        const result = a / b;
        this.history.push(`${a} / ${b} = ${result}`);
        return result;
    }

    getHistory() {
        return [...this.history];
    }

    clearHistory() {
        this.history = [];
    }
}
'''
        (src_dir / "calculator.js").write_text(calculator_content)
    
    def _create_javascript_tests(self, project_dir: Path, name: str) -> None:
        """Create JavaScript tests."""
        test_dir = project_dir / "test"
        
        # Create Jest configuration
        jest_config = {
            "testEnvironment": "node",
            "collectCoverageFrom": ["src/**/*.js"],
            "coverageDirectory": "coverage"
        }
        
        (project_dir / "jest.config.json").write_text(json.dumps(jest_config, indent=2))
        
        # Create calculator tests
        test_content = '''/**
 * Tests for Calculator class
 */

import { Calculator } from '../src/calculator.js';

describe('Calculator', () => {
    let calculator;

    beforeEach(() => {
        calculator = new Calculator();
    });

    test('should add two numbers', () => {
        const result = calculator.add(2, 3);
        expect(result).toBe(5);
        expect(calculator.getHistory()).toContain('2 + 3 = 5');
    });

    test('should throw error when dividing by zero', () => {
        expect(() => calculator.divide(10, 0)).toThrow('Cannot divide by zero');
    });

    test('should track calculation history', () => {
        calculator.add(1, 2);
        calculator.multiply(3, 4);
        
        const history = calculator.getHistory();
        expect(history).toHaveLength(2);
        expect(history).toContain('1 + 2 = 3');
        expect(history).toContain('3 * 4 = 12');
    });
});
'''
        (test_dir / "calculator.test.js").write_text(test_content)
    
    def _create_javascript_config(self, project_dir: Path) -> None:
        """Create JavaScript configuration files."""
        # ESLint config
        eslint_config = {
            "env": {
                "es2022": True,
                "node": True,
                "jest": True
            },
            "extends": ["eslint:recommended"],
            "parserOptions": {
                "ecmaVersion": "latest",
                "sourceType": "module"
            }
        }
        (project_dir / ".eslintrc.json").write_text(json.dumps(eslint_config, indent=2))
    
    def _create_javascript_docs(self, project_dir: Path, name: str) -> None:
        """Create JavaScript documentation."""
        readme_content = f'''# {name}

A realistic JavaScript test project.

## Installation

```bash
npm install
```

## Usage

```bash
npm start
npm test
```

## License

MIT License
'''
        (project_dir / "README.md").write_text(readme_content)
    
    def _create_javascript_ci(self, project_dir: Path, name: str) -> None:
        """Create JavaScript CI configuration."""
        workflows_dir = project_dir / ".github" / "workflows"
        
        ci_content = '''name: CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Use Node.js
      uses: actions/setup-node@v3
      with:
        node-version: "18.x"
    - name: Install dependencies
      run: npm ci
    - name: Run tests
      run: npm test
'''
        (workflows_dir / "ci.yml").write_text(ci_content)
    
    def _create_mixed_python_backend(self, project_dir: Path, name: str) -> None:
        """Create Python backend for mixed project."""
        backend_dir = project_dir / "backend"
        
        # Create simple FastAPI backend
        (backend_dir / "main.py").write_text('''"""FastAPI backend for mixed project."""

from fastapi import FastAPI

app = FastAPI(title="Mixed Project Backend")

@app.get("/")
async def root():
    return {"message": "Mixed project backend"}

@app.get("/api/health")
async def health():
    return {"status": "healthy"}
''')
        
        (backend_dir / "requirements.txt").write_text("fastapi>=0.100.0\\nuvicorn>=0.22.0\\n")
    
    def _create_mixed_javascript_frontend(self, project_dir: Path, name: str) -> None:
        """Create JavaScript frontend for mixed project."""
        frontend_dir = project_dir / "frontend"
        
        # Create simple Express frontend
        (frontend_dir / "package.json").write_text(json.dumps({
            "name": f"{name}-frontend",
            "version": "1.0.0",
            "scripts": {
                "start": "node server.js"
            },
            "dependencies": {
                "express": "^4.18.0"
            }
        }, indent=2))
        
        (frontend_dir / "server.js").write_text('''const express = require('express');
const app = express();
const port = 3000;

app.get('/', (req, res) => {
    res.send('Mixed project frontend');
});

app.listen(port, () => {
    console.log(`Frontend server running at http://localhost:${port}`);
});
''')
    
    def _create_mixed_shared_config(self, project_dir: Path, name: str) -> None:
        """Create shared configuration for mixed project."""
        # Create docker-compose.yml
        (project_dir / "docker-compose.yml").write_text('''version: '3.8'
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend
''')
    
    def _create_mixed_docs(self, project_dir: Path, name: str) -> None:
        """Create documentation for mixed project."""
        readme_content = f'''# {name}

A realistic mixed-language project with Python backend and JavaScript frontend.

## Architecture

- **Backend**: Python FastAPI application
- **Frontend**: JavaScript/Node.js application

## Development

```bash
# Start full stack
docker-compose up --build

# Backend only
cd backend && python -m uvicorn main:app --reload

# Frontend only  
cd frontend && npm start
```
'''
        (project_dir / "README.md").write_text(readme_content)
    
    def _create_mixed_ci(self, project_dir: Path, name: str) -> None:
        """Create CI configuration for mixed project."""
        workflows_dir = project_dir / ".github" / "workflows"
        
        ci_content = '''name: CI

on:
  push:
    branches: [ main ]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: "3.10"
    - name: Install backend dependencies
      run: |
        cd backend
        pip install -r requirements.txt

  frontend:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Use Node.js
      uses: actions/setup-node@v3
      with:
        node-version: "18.x"
    - name: Install frontend dependencies
      run: |
        cd frontend
        npm ci
'''
        (workflows_dir / "ci.yml").write_text(ci_content)
    
    def _initialize_git_repo(self, project_dir: Path, name: str, project_type: str) -> None:
        """Initialize Git repository with realistic history."""
        try:
            # Initialize repository
            subprocess.run(["git", "init"], cwd=project_dir, check=True, capture_output=True)
            
            # Configure git for testing
            subprocess.run(["git", "config", "user.name", "Test User"], 
                         cwd=project_dir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], 
                         cwd=project_dir, check=True, capture_output=True)
            
            # Create .gitignore
            gitignore_content = self._get_gitignore_content(project_type)
            (project_dir / ".gitignore").write_text(gitignore_content)
            
            # Initial commit
            subprocess.run(["git", "add", "."], cwd=project_dir, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", f"Initial commit: {name} project setup"], 
                         cwd=project_dir, check=True, capture_output=True)
            
        except subprocess.CalledProcessError as e:
            # Git initialization failed, but don't fail the entire project creation
            print(f"Warning: Git initialization failed for {name}: {e}")
    
    def _get_gitignore_content(self, project_type: str) -> str:
        """Get appropriate .gitignore content for project type."""
        if project_type == "python":
            return '''# Python
__pycache__/
*.py[cod]
*.so
.Python
build/
dist/
*.egg-info/

# Testing
.pytest_cache/
.coverage
htmlcov/

# Virtual environments
.env
.venv
venv/

# IDEs
.vscode/
.idea/

# OS
.DS_Store
'''
        elif project_type == "javascript":
            return '''# Dependencies
node_modules/
npm-debug.log*

# Build outputs
dist/
build/

# Runtime
.env

# Testing
coverage/

# IDEs
.vscode/
.idea/

# OS
.DS_Store
'''
        else:  # mixed
            return '''# Python
__pycache__/
*.py[cod]
*.so
.Python
build/
dist/
*.egg-info/

# JavaScript
node_modules/
npm-debug.log*

# Build outputs
dist/
build/

# Testing
.pytest_cache/
.coverage
coverage/

# Virtual environments
.env
.venv
venv/

# IDEs
.vscode/
.idea/

# OS
.DS_Store
'''