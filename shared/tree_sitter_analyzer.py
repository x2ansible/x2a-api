"""
shared/tree_sitter_analyzer.py
Modern, production-grade Tree-sitter Analyzer for Chef (and other IaC)
- Full AST traversal and robust Chef resource/metadata extraction.
- Falls back to patterns only as needed.
- Easily extensible for other languages.
"""

import logging
import os
import yaml
import re
from typing import Dict, Any, List, Optional

logger = logging.getLogger("TreeSitterAnalyzer")
logger.setLevel(logging.INFO)


class TreeSitterAnalyzer:
    def __init__(self, config_path: Optional[str] = None):
        self.logger = logger
        self.config = self._load_config(config_path)
        self.parsers, self.languages = {}, {}
        self.enabled, self.init_method = False, "none"
        self.error = None
        self._initialize_tree_sitter()

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

    def _initialize_tree_sitter(self):
        try:
            from tree_sitter_languages import get_parser, get_language
            for lang in self.config['supported_languages']:
                try:
                    self.parsers[lang] = get_parser(lang)
                    self.languages[lang] = get_language(lang)
                except Exception:
                    continue
            if self.parsers:
                self.enabled = True
                self.init_method = "tree_sitter_languages"
                logger.info("Tree-sitter initialized.")
        except Exception as e:
            self.error = str(e)
            self.enabled = False
            self.init_method = "pattern"
            logger.warning("Tree-sitter unavailable, pattern-only mode.")

    def is_enabled(self) -> bool:
        return self.enabled

    # ---- AST Traversal & Extraction ----

    def extract_chef_facts(self, files: Dict[str, str]) -> Dict[str, Any]:
        facts = {
            'metadata': {},
            'resources': {k: [] for k in [
                "packages", "services", "files", "templates", "directories", "users", "groups"
            ]},
            'dependencies': {'cookbook_deps': [], 'include_recipes': []},
            'syntax_validation': {},
            'tree_sitter_enabled': self.is_enabled(),
            'extraction_method': self.init_method,
            'debug_ast': {}
        }
        for filename, content in files.items():
            if filename == "metadata.rb":
                facts['metadata'] = self._extract_chef_metadata(content)
                facts['dependencies']['cookbook_deps'] = facts['metadata'].get('depends', [])
            elif filename.endswith(".rb"):
                # AST-based resource extraction (preferred)
                ast_result = None
                if self.is_enabled():
                    try:
                        ast_result = self._extract_chef_resources_from_ast(content)
                        facts['debug_ast'][filename] = self._debug_ast_sexp(content)
                    except Exception as e:
                        logger.warning(f"AST extraction failed: {e}")
                # Pattern fallback
                pattern_result = self._extract_chef_resources_patterns(content)
                used = ast_result if ast_result and sum(len(v) for v in ast_result.values()) > 0 else pattern_result
                for k, v in used.items():
                    facts['resources'][k].extend(v)
                # Also extract include_recipes (AST then pattern fallback)
                includes = self._extract_include_recipes_ast(content) if self.is_enabled() else []
                if not includes:
                    includes = self._extract_include_recipes_pattern(content)
                facts['dependencies']['include_recipes'].extend(includes)
            # Syntax validation per file
            facts['syntax_validation'][filename] = self.validate_syntax(content, filename)
        # Deduplication
        for k in facts['resources']:
            facts['resources'][k] = list(dict.fromkeys(facts['resources'][k]))
        facts['dependencies']['cookbook_deps'] = list(dict.fromkeys(facts['dependencies']['cookbook_deps']))
        facts['dependencies']['include_recipes'] = list(dict.fromkeys(facts['dependencies']['include_recipes']))
        # Summary
        facts['summary'] = {
            "total_resources": sum(len(v) for v in facts['resources'].values()),
            "total_dependencies": len(facts['dependencies']['cookbook_deps']) + len(facts['dependencies']['include_recipes']),
            "extraction_method": self.init_method,
        }
        return facts

    def _extract_chef_resources_from_ast(self, content: str) -> Dict[str, List[str]]:
        parser = self.parsers.get("ruby")
        if not parser:
            return {k: [] for k in [
                "packages", "services", "files", "templates", "directories", "users", "groups"
            ]}
        tree = parser.parse(content.encode())
        out = {k: [] for k in [
            "packages", "services", "files", "templates", "directories", "users", "groups"
        ]}
        resource_map = {
            "package": "packages", "service": "services", "file": "files",
            "cookbook_file": "files", "remote_file": "files", "template": "templates",
            "directory": "directories", "user": "users", "group": "groups"
        }
        def traverse(node):
            # Look for all calls and commands, regardless of nesting
            if getattr(node, 'type', '') in ("call", "method_call", "command", "command_call"):
                method = None
                for c in getattr(node, 'children', []):
                    if getattr(c, 'type', '') == 'identifier':
                        method = c.text.decode() if isinstance(c.text, bytes) else str(c.text)
                        break
                if method and method in resource_map:
                    arg = self._find_first_string_arg(node)
                    if arg:
                        out[resource_map[method]].append(arg)
            for c in getattr(node, 'children', []):
                traverse(c)
        traverse(tree.root_node)
        return out

    def _find_first_string_arg(self, node):
        """Traverse children up to depth 3 to find the first string literal."""
        def walk(n, d=0):
            if d > 3: return None
            # Any string-type node
            if "string" in getattr(n, 'type', ''):
                val = self._extract_string_content(n)
                if val: return val
            for c in getattr(n, 'children', []):
                val = walk(c, d + 1)
                if val: return val
            return None
        return walk(node)

    def _extract_string_content(self, node):
        if hasattr(node, 'children'):
            for c in node.children:
                if "content" in getattr(c, 'type', '') and hasattr(c, "text"):
                    return c.text.decode() if isinstance(c.text, bytes) else str(c.text)
        if hasattr(node, "text"):
            t = node.text.decode() if isinstance(node.text, bytes) else str(node.text)
            return t.strip("\"'")
        return None

    # ---- Pattern fallback ----

    def _extract_chef_resources_patterns(self, content: str) -> Dict[str, List[str]]:
        patt = {
            "packages": [r'package\s+["\']([^"\']+)["\']'],
            "services": [r'service\s+["\']([^"\']+)["\']'],
            "files": [r'(?:file|cookbook_file|remote_file)\s+["\']([^"\']+)["\']'],
            "templates": [r'template\s+["\']([^"\']+)["\']'],
            "directories": [r'directory\s+["\']([^"\']+)["\']'],
            "users": [r'user\s+["\']([^"\']+)["\']'],
            "groups": [r'group\s+["\']([^"\']+)["\']'],
        }
        found = {k: [] for k in patt}
        for k, plist in patt.items():
            for p in plist:
                found[k] += re.findall(p, content)
        return found

    # ---- Metadata & Dependency Extraction ----

    def _extract_chef_metadata(self, content: str) -> Dict[str, Any]:
        meta = {}
        for k in ["name", "version", "description", "maintainer", "license", "chef_version"]:
            m = re.search(rf'{k}\s+["\']([^"\']+)["\']', content)
            if m: meta[k] = m.group(1)
        meta['depends'] = re.findall(r'depends\s+["\']([^"\']+)["\']', content)
        return meta

    def _extract_include_recipes_ast(self, content: str) -> List[str]:
        parser = self.parsers.get("ruby")
        if not parser: return []
        tree = parser.parse(content.encode())
        found = []
        def traverse(node):
            if getattr(node, 'type', '') in ("call", "command", "method_call", "command_call"):
                method = None
                for c in getattr(node, 'children', []):
                    if getattr(c, 'type', '') == 'identifier':
                        method = c.text.decode() if isinstance(c.text, bytes) else str(c.text)
                        break
                if method == "include_recipe":
                    arg = self._find_first_string_arg(node)
                    if arg: found.append(arg)
            for c in getattr(node, 'children', []):
                traverse(c)
        traverse(tree.root_node)
        return found

    def _extract_include_recipes_pattern(self, content: str) -> List[str]:
        return re.findall(r'include_recipe\s+["\']([^"\']+)["\']', content)

    # ---- Syntax & Language Detection ----

    def validate_syntax(self, content: str, filename: Optional[str] = None) -> Dict[str, Any]:
        lang = self.detect_language(content, filename)
        if self.is_enabled() and lang in self.parsers:
            try:
                tree = self.parsers[lang].parse(content.encode())
                valid = not getattr(tree.root_node, 'has_error', False)
                return {"valid": valid, "language": lang, "method": "tree_sitter"}
            except Exception:
                pass
        if lang == "yaml":
            try:
                yaml.safe_load(content)
                return {"valid": True, "language": "yaml", "method": "yaml"}
            except yaml.YAMLError:
                return {"valid": False, "language": "yaml", "method": "yaml"}
        return {"valid": True, "language": lang, "method": "fallback"}

    def detect_language(self, content: str, filename: Optional[str] = None) -> str:
        if filename:
            ext = filename.lower()
            if ext.endswith(".rb"): return "ruby"
            if ext.endswith((".yml", ".yaml")): return "yaml"
        c = content.lower()
        if 'package ' in c or 'service ' in c: return "ruby"
        if "---" in c or "hosts:" in c: return "yaml"
        return "unknown"

    # ---- AST Debug ----

    def _debug_ast_sexp(self, content: str) -> str:
        parser = self.parsers.get("ruby")
        if not parser: return ""
        tree = parser.parse(content.encode())
        return tree.root_node.sexp() if hasattr(tree.root_node, "sexp") else ""

    # ---- Diagnostics ----

    def get_status(self) -> Dict[str, Any]:
        return {
            'enabled': self.enabled,
            'init_method': self.init_method,
            'parsers_loaded': list(self.parsers.keys()),
            'version': 'tree-sitter-analyzer-v3.5',
            'error': self.error,
        }

    # ---- Quick tests ----

    def quick_test(self):
        files = {
            "metadata.rb": 'name "apache"\nversion "1.0.0"\nchef_version ">= 15.0"',
            "recipes/default.rb": 'package "httpd" do\n  action :install\nend'
        }
        result = self.extract_chef_facts(files)
        print(result['resources'])
        print("Total resources:", result['summary']['total_resources'])

    def full_test(self):
        files = {
            'metadata.rb': '''name "apache"
version "1.0.0"
chef_version ">= 15.0"
description "Installs and configures Apache HTTP Server"
maintainer "Test Chef"
maintainer_email "test@example.com"
license "Apache-2.0"
depends "apt"
depends "build-essential"
supports "ubuntu"''',
            'recipes/default.rb': '''# Default recipe for Apache
package "httpd" do
  action :install
end
package "httpd-devel" do
  action :install
  only_if { node['apache']['install_devel'] }
end
service "httpd" do
  action [:enable, :start]
  supports restart: true, reload: true
end
template "/etc/httpd/conf/httpd.conf" do
  source "httpd.conf.erb"
  owner "root"
  group "root"
  mode "0644"
  variables(
    port: node['apache']['port'],
    servername: node['apache']['servername']
  )
  notifies :restart, "service[httpd]", :delayed
end
cookbook_file "/var/www/html/index.html" do
  source "index.html"
  owner "apache"
  group "apache"
  mode "0644"
end
directory "/var/log/httpd" do
  owner "apache"
  group "apache"
  mode "0755"
  recursive true
end
user "apache" do
  comment "Apache User"
  home "/var/www"
  shell "/bin/false"
  system true
end
include_recipe "apache::ssl"
include_recipe "apache::mod_rewrite"''',
            'recipes/ssl.rb': '''# SSL configuration recipe
package "mod_ssl" do
  action :install
end
service "httpd" do
  action :nothing
end
template "/etc/httpd/conf.d/ssl.conf" do
  source "ssl.conf.erb"
  owner "root"
  group "root"
  mode "0644"
  notifies :reload, "service[httpd]"
end'''
        }
        facts = self.extract_chef_facts(files)
        print(f"Resources: {facts['resources']}")
        print(f"Summary: {facts['summary']}")


if __name__ == "__main__":
    TreeSitterAnalyzer().quick_test()
    TreeSitterAnalyzer().full_test()
