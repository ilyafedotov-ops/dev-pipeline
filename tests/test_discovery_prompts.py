"""Test discovery prompt system functionality."""

import tempfile
import unittest
from pathlib import Path

from tests.harness.components.discovery import DiscoveryTestComponent


class TestDiscoveryPrompts(unittest.TestCase):
    """Test discovery prompt selection and project type detection."""
    
    def setUp(self):
        self.discovery_component = DiscoveryTestComponent()
    
    def test_detect_python_project_type(self):
        """Test detection of Python project type."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "python_project"
            project_path.mkdir()
            
            # Create Python project indicators
            (project_path / "setup.py").write_text("from setuptools import setup")
            (project_path / "src").mkdir()
            (project_path / "src" / "main.py").write_text("print('hello')")
            
            project_type = self.discovery_component._detect_project_type(project_path)
            self.assertEqual(project_type, "python")
    
    def test_detect_javascript_project_type(self):
        """Test detection of JavaScript project type."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "js_project"
            project_path.mkdir()
            
            # Create JavaScript project indicators
            (project_path / "package.json").write_text('{"name": "test"}')
            (project_path / "src").mkdir()
            (project_path / "src" / "index.js").write_text("console.log('hello');")
            
            project_type = self.discovery_component._detect_project_type(project_path)
            self.assertEqual(project_type, "javascript")
    
    def test_detect_mixed_project_type(self):
        """Test detection of mixed project type."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "mixed_project"
            project_path.mkdir()
            
            # Create mixed project indicators
            (project_path / "package.json").write_text('{"name": "test"}')
            (project_path / "setup.py").write_text("from setuptools import setup")
            (project_path / "src").mkdir()
            (project_path / "src" / "index.js").write_text("console.log('hello');")
            (project_path / "src" / "main.py").write_text("print('hello')")
            
            project_type = self.discovery_component._detect_project_type(project_path)
            self.assertEqual(project_type, "mixed")
    
    def test_detect_demo_project_type(self):
        """Test detection of demo project type."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "demo_bootstrap"
            project_path.mkdir()
            
            # Create demo project indicators
            (project_path / "README.md").write_text("# Demo Project\nThis is a demo application.")
            (project_path / "app.py").write_text("print('demo')")
            
            project_type = self.discovery_component._detect_project_type(project_path)
            self.assertEqual(project_type, "demo")
    
    def test_get_discovery_prompt_path_python(self):
        """Test getting Python discovery prompt path."""
        prompt_path = self.discovery_component._get_discovery_prompt_path("python")
        self.assertTrue(prompt_path.exists())
        self.assertEqual(prompt_path.name, "python-discovery.prompt.md")
    
    def test_get_discovery_prompt_path_javascript(self):
        """Test getting JavaScript discovery prompt path."""
        prompt_path = self.discovery_component._get_discovery_prompt_path("javascript")
        self.assertTrue(prompt_path.exists())
        self.assertEqual(prompt_path.name, "javascript-discovery.prompt.md")
    
    def test_get_discovery_prompt_path_mixed(self):
        """Test getting mixed project discovery prompt path."""
        prompt_path = self.discovery_component._get_discovery_prompt_path("mixed")
        self.assertTrue(prompt_path.exists())
        self.assertEqual(prompt_path.name, "mixed-project-discovery.prompt.md")
    
    def test_get_discovery_prompt_path_demo(self):
        """Test getting demo project discovery prompt path."""
        prompt_path = self.discovery_component._get_discovery_prompt_path("demo")
        self.assertTrue(prompt_path.exists())
        self.assertEqual(prompt_path.name, "demo-project-discovery.prompt.md")
    
    def test_get_discovery_prompt_path_fallback(self):
        """Test fallback to generic prompt for unknown project types."""
        prompt_path = self.discovery_component._get_discovery_prompt_path("unknown")
        self.assertTrue(prompt_path.exists())
        self.assertEqual(prompt_path.name, "repo-discovery.prompt.md")
    
    def test_all_prompt_files_exist(self):
        """Test that all expected prompt files exist."""
        prompts_dir = Path(__file__).resolve().parents[1] / "prompts"
        
        expected_prompts = [
            "repo-discovery.prompt.md",
            "python-discovery.prompt.md", 
            "javascript-discovery.prompt.md",
            "mixed-project-discovery.prompt.md",
            "demo-project-discovery.prompt.md"
        ]
        
        for prompt_name in expected_prompts:
            prompt_path = prompts_dir / prompt_name
            self.assertTrue(prompt_path.exists(), f"Missing prompt file: {prompt_name}")
            
            # Verify the prompt has content
            content = prompt_path.read_text(encoding='utf-8')
            self.assertGreater(len(content.strip()), 100, f"Prompt file {prompt_name} appears to be empty or too short")


if __name__ == '__main__':
    unittest.main()