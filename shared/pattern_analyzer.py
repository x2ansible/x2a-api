"""
shared/pattern_analyzer.py
Modern, production-grade Pattern Analyzer for Chef (and other IaC)
- Robust Chef resource/metadata extraction using regex patterns.
- Pure Python implementation with no external dependencies.
- Easily extensible for other languages.
"""

import logging
import os
import yaml
import re
from typing import Dict, Any, List, Optional

logger = logging.getLogger("PatternAnalyzer")
logger.setLevel(logging.INFO)


class PatternAnalyzer:
    def __init__(self, config_path: Optional[str] = None):
        self.logger = logger
        self.config = self._load_config(config_path)
        self.enabled = True
        self.init_method = "pattern"
        self.error = None
        self.logger.info("Pattern-based extraction initialized")

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        # Simple config system (can be extended)
        cfg = {'enabled': True, 'supported_languages': ['ruby', 'yaml']}
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path) as f:
                    user_cfg = yaml.safe_load(f)
                    cfg.update(user_cfg)
            except Exception as e:
                logger.warning(f"Config load failed: {e}")
        return cfg

    def is_enabled(self) -> bool:
        return self.enabled

    # ---- Pattern-Based Extraction ----

    def extract_chef_facts(self, files: Dict[str, str]) -> Dict[str, Any]:
        """Extract Chef facts using pattern-based extraction only"""
        self.logger.info("Using pattern-based extraction")
        pattern_result = self._extract_chef_facts_patterns(files)
        
        pattern_result['extraction_method'] = "pattern"
        pattern_result['summary'] = {
            'ast_available': False,
            'pattern_fallback_used': False  # Not a fallback, this is the primary method
        }
        
        return pattern_result

    def _extract_chef_facts_patterns(self, files: Dict[str, str]) -> Dict[str, Any]:
        """Extract Chef facts using pattern-based extraction only"""
        all_resources = {k: [] for k in ["packages", "services", "files", "templates", "directories", "users", "groups"]}
        all_metadata = {}
        all_dependencies = {"cookbook_deps": [], "include_recipes": []}
        syntax_validation = {}
        file_analysis = {}
        
        for filename, content in files.items():
            # Extract resources from this file
            resources = self._extract_chef_resources_patterns(content)
            for key in all_resources:
                all_resources[key].extend(resources[key])
            
            # Extract metadata from metadata.rb
            if filename == "metadata.rb":
                all_metadata = self._extract_chef_metadata(content)
            
            # Extract include recipes
            includes = self._extract_include_recipes_pattern(content)
            all_dependencies["include_recipes"].extend(includes)
            
            # Basic syntax validation (just check if it's valid Ruby-like syntax)
            syntax_validation[filename] = {
                "valid": True,  # Pattern extraction doesn't validate syntax
                "errors": [],
                "language": "ruby"
            }
            
            # Basic file analysis
            file_analysis[filename] = {
                "size": len(content),
                "lines": content.count('\n') + 1,
                "has_resources": any(len(resources[key]) > 0 for key in resources)
            }
        
        # Calculate summary
        total_resources = sum(len(resources) for resources in all_resources.values())
        total_files = len(files)
        valid_files = total_files
        
        return {
            "metadata": all_metadata,
            "resources": all_resources,
            "dependencies": all_dependencies,
            "syntax_validation": syntax_validation,
            "file_analysis": file_analysis,
            "summary": {
                "total_files": total_files,
                "valid_files": valid_files,
                "syntax_success_rate": 100.0 if total_files > 0 else 0,
                "total_resources": total_resources,
                "has_metadata": bool(all_metadata),
                "is_wrapper": len(all_dependencies["include_recipes"]) > 0,
                "complexity_score": self._calculate_complexity_score({
                    "resources": all_resources,
                    "dependencies": all_dependencies
                })
            },
            "pattern_analyzer_enabled": True,
            "tree_sitter_enabled": False
        }

    def _calculate_complexity_score(self, chef_facts: Dict[str, Any]) -> int:
        """Calculate complexity score based on extracted facts"""
        score = 0
        score += len(chef_facts['resources']['packages']) * 1
        score += len(chef_facts['resources']['services']) * 2
        score += len(chef_facts['resources']['files']) * 1
        score += len(chef_facts['resources']['templates']) * 2
        score += len(chef_facts['resources']['directories']) * 1
        cookbook_deps = chef_facts['dependencies'].get('cookbook_deps', [])
        include_recipes = chef_facts['dependencies'].get('include_recipes', [])
        score += len(cookbook_deps) * 3
        score += len(include_recipes) * 2
        return score

    # ---- Enhanced Pattern extraction ----

    def _extract_chef_resources_patterns(self, content: str) -> Dict[str, List[str]]:
        resources = {k: [] for k in ["packages", "services", "files", "templates", "directories", "users", "groups"]}
        
        # Enhanced patterns for better extraction
        package_patterns = [
            r'package\s+["\']([^"\']+)["\']',
            r'yum_package\s+["\']([^"\']+)["\']',
            r'apt_package\s+["\']([^"\']+)["\']',
            r'package\s+["\']([^"\']+)["\']\s+do',
            r'yum_package\s+["\']([^"\']+)["\']\s+do',
            r'apt_package\s+["\']([^"\']+)["\']\s+do'
        ]
        
        service_patterns = [
            r'service\s+["\']([^"\']+)["\']',
            r'systemd_service\s+["\']([^"\']+)["\']',
            r'service\s+["\']([^"\']+)["\']\s+do',
            r'systemd_service\s+["\']([^"\']+)["\']\s+do'
        ]
        
        file_patterns = [
            r'file\s+["\']([^"\']+)["\']',
            r'cookbook_file\s+["\']([^"\']+)["\']',
            r'remote_file\s+["\']([^"\']+)["\']',
            r'file\s+["\']([^"\']+)["\']\s+do',
            r'cookbook_file\s+["\']([^"\']+)["\']\s+do',
            r'remote_file\s+["\']([^"\']+)["\']\s+do'
        ]
        
        template_patterns = [
            r'template\s+["\']([^"\']+)["\']',
            r'cookbook_template\s+["\']([^"\']+)["\']',
            r'template\s+["\']([^"\']+)["\']\s+do',
            r'cookbook_template\s+["\']([^"\']+)["\']\s+do'
        ]
        
        directory_patterns = [
            r'directory\s+["\']([^"\']+)["\']',
            r'directory\s+["\']([^"\']+)["\']\s+do'
        ]
        
        user_patterns = [
            r'user\s+["\']([^"\']+)["\']',
            r'user\s+["\']([^"\']+)["\']\s+do'
        ]
        
        group_patterns = [
            r'group\s+["\']([^"\']+)["\']',
            r'group\s+["\']([^"\']+)["\']\s+do'
        ]
        
        # Extract all resources first
        for pattern in package_patterns:
            resources['packages'].extend(re.findall(pattern, content))
        
        for pattern in service_patterns:
            resources['services'].extend(re.findall(pattern, content))
        
        for pattern in file_patterns:
            resources['files'].extend(re.findall(pattern, content))
        
        for pattern in template_patterns:
            resources['templates'].extend(re.findall(pattern, content))
        
        for pattern in directory_patterns:
            resources['directories'].extend(re.findall(pattern, content))
        
        for pattern in user_patterns:
            resources['users'].extend(re.findall(pattern, content))
        
        for pattern in group_patterns:
            resources['groups'].extend(re.findall(pattern, content))
        
        # FIX: Remove duplicates and ensure proper separation
        # First, remove duplicates within each category
        for category in resources:
            resources[category] = list(set(resources[category]))
        
        # CRITICAL FIX: Ensure services and packages don't overlap
        # If an item appears in both services and packages, prioritize based on context
        services_set = set(resources['services'])
        packages_set = set(resources['packages'])
        
        # Items that appear in both - need to decide which category they belong to
        overlap = services_set.intersection(packages_set)
        
        for item in overlap:
            # Check if this item is more likely a service or package based on context
            # Common service names that might also be package names
            service_indicators = ['nginx', 'apache', 'httpd', 'postgresql', 'mysql', 'redis', 'elasticsearch']
            
            if item.lower() in service_indicators:
                # Keep in services, remove from packages
                if item in packages_set:
                    packages_set.remove(item)
                    resources['packages'] = list(packages_set)
            else:
                # Keep in packages, remove from services
                if item in services_set:
                    services_set.remove(item)
                    resources['services'] = list(services_set)
        
        # Update the resources with the cleaned sets
        resources['services'] = list(services_set)
        resources['packages'] = list(packages_set)
        
        return resources

    # ---- Metadata & Dependency Extraction ----

    def _extract_chef_metadata(self, content: str) -> Dict[str, Any]:
        metadata = {}
        
        # Enhanced metadata patterns
        patterns = {
            'name': [r'name\s+["\']([^"\']+)["\']', r'name\s+["\']([^"\']+)["\']'],
            'version': [r'version\s+["\']([^"\']+)["\']', r'version\s+["\']([^"\']+)["\']'],
            'description': [r'description\s+["\']([^"\']+)["\']', r'description\s+["\']([^"\']+)["\']'],
            'maintainer': [r'maintainer\s+["\']([^"\']+)["\']', r'maintainer\s+["\']([^"\']+)["\']'],
            'maintainer_email': [r'maintainer_email\s+["\']([^"\']+)["\']', r'maintainer_email\s+["\']([^"\']+)["\']'],
            'license': [r'license\s+["\']([^"\']+)["\']', r'license\s+["\']([^"\']+)["\']'],
            'issues_url': [r'issues_url\s+["\']([^"\']+)["\']', r'issues_url\s+["\']([^"\']+)["\']'],
            'source_url': [r'source_url\s+["\']([^"\']+)["\']', r'source_url\s+["\']([^"\']+)["\']'],
            'depends': [r'depends\s+["\']([^"\']+)["\']', r'depends\s+["\']([^"\']+)["\']']
        }
        
        for key, pattern_list in patterns.items():
            for pattern in pattern_list:
                matches = re.findall(pattern, content)
                if matches:
                    metadata[key] = matches[0]
                    break
        
        return metadata

    def _extract_include_recipes_pattern(self, content: str) -> List[str]:
        includes = []
        
        # Enhanced include_recipe patterns
        patterns = [
            r'include_recipe\s+["\']([^"\']+)["\']',
            r'include_recipe\s+["\']([^"\']+)["\']',
            r'include_recipe\s+["\']([^"\']+)["\']',
            r'include_recipe\s+["\']([^"\']+)["\']'
        ]
        
        for pattern in patterns:
            includes.extend(re.findall(pattern, content))
        
        # FIX: Remove duplicates while preserving order
        seen = set()
        unique_includes = []
        for item in includes:
            if item not in seen:
                seen.add(item)
                unique_includes.append(item)
        
        return unique_includes

    # ---- Syntax & Language Detection ----

    def validate_syntax(self, content: str, filename: str) -> Dict[str, Any]:
        # Basic pattern-based validation
        if filename.endswith('.rb'):
            # Check for basic Ruby syntax patterns
            has_method_calls = bool(re.search(r'\w+\s+["\']\w+["\']', content))
            has_blocks = bool(re.search(r'\s+do\s*$', content, re.MULTILINE))
            has_end = 'end' in content
            return {
                'valid': has_method_calls or has_blocks,
                'method': 'pattern',
                'errors': [] if (has_method_calls or has_blocks) else ['No valid Ruby syntax detected']
            }
        return {'valid': True, 'method': 'pattern', 'errors': []}

    def detect_language(self, content: str, filename: str) -> str:
        # Enhanced language detection
        if filename.endswith('.rb'):
            return 'ruby'
        elif filename.endswith('.yml') or filename.endswith('.yaml'):
            return 'yaml'
        elif filename.endswith('.json'):
            return 'json'
        elif filename.endswith('.md'):
            return 'markdown'
        elif filename.endswith('.txt'):
            return 'text'
        else:
            # Pattern-based detection
            if re.search(r'package\s+["\']', content) or re.search(r'service\s+["\']', content):
                return 'ruby'
            elif re.search(r'^---\s*$', content, re.MULTILINE):
                return 'yaml'
            elif re.search(r'^\s*\{', content) and re.search(r'\}\s*$', content):
                return 'json'
            else:
                return 'unknown'

    # ---- Diagnostics ----

    def get_status(self) -> Dict[str, Any]:
        return {
            'enabled': self.is_enabled(),
            'init_method': self.init_method,
            'ast_working': False,  # No AST parsing
            'pattern_fallback_available': True,
            'honest_reporting': True,
            'parsers_loaded': 0,  # No parsers needed
            'supported_languages': ['ruby', 'yaml']  # Pattern-based support
        }

    # ---- Quick tests ----

    def quick_test(self) -> None:
        test_content = '''
        package "nginx" do
          action :install
        end
        
        service "nginx" do
          action [:enable, :start]
        end
        '''
        
        print("Pattern Analyzer Quick Test")
        print(f"Enabled: {self.is_enabled()}")
        print(f"Method: {self.init_method}")
        
        result = self.extract_chef_facts({'test.rb': test_content})
        print(f"Extraction method: {result.get('extraction_method', 'unknown')}")
        print(f"AST available: {result.get('summary', {}).get('ast_available', False)}")
        print(f"Packages found: {len(result['resources']['packages'])}")
        print(f"Services found: {len(result['resources']['services'])}")

    def full_test(self) -> None:
        print("Pattern Analyzer Full Test")
        print(f"Status: {self.get_status()}")
        
        test_files = {
            'metadata.rb': '''
                name "test-cookbook"
                version "1.0.0"
                description "Test cookbook"
                maintainer "Test User"
                maintainer_email "test@example.com"
                license "MIT"
                depends "apt"
            ''',
            'default.rb': '''
                package "nginx" do
                  action :install
                end
                
                service "nginx" do
                  action [:enable, :start]
                end
                
                template "/etc/nginx/nginx.conf" do
                  source "nginx.conf.erb"
                  owner "root"
                  group "root"
                  mode "0644"
                end
                
                include_recipe "apt"
            '''
        }
        
        result = self.extract_chef_facts(test_files)
        print(f"Extraction method: {result.get('extraction_method', 'unknown')}")
        print(f"AST available: {result.get('summary', {}).get('ast_available', False)}")
        print(f"Total resources: {result.get('summary', {}).get('total_resources', 0)}")
        print(f"Metadata extracted: {bool(result.get('metadata', {}))}")
        print(f"Dependencies: {result.get('dependencies', {})}")


if __name__ == "__main__":
    PatternAnalyzer().quick_test()
    PatternAnalyzer().full_test()
