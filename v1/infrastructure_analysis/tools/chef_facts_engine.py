#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Chef Facts Extractor (production-ready, documented)

===============================================================================
SCHEMA AT A GLANCE (JSON)
===============================================================================
{
  "schema": "chef-facts@1",
  "cookbook": "<cookbook-name>",
  "recipes": [
    {
      "name": "default",
      "file": "recipes/default.rb",
      "includes": ["apache2::default"],             # static include_recipe targets
      "includes_dynamic": ["#{cookbook_name}::x"],  # dynamic targets (interpolation/vars)
      "attributes_read": ["node['x']['y']"],
      "resources": [
        {
          "rid": "template[/etc/httpd/conf/httpd.conf]",      # type[name or name_expr]
          "type": "template",
          "name": "/etc/httpd/conf/httpd.conf",               # literal title if available
          "name_expr": None,                                  # raw expression if non-literal
          "actions": ["create"],                              # actions set inside block
          "guards": [{"type": "only_if", "expr": "cmd ..."}],
          "notifies": [{"action":"restart","target":"service[httpd]","timing":"delayed","source":{"file":"...","lines":[10,10]}}],
          "subscribes": [],
          "properties": { "source": ["httpd.conf.erb"], "variables_keys": ["port","server_admin"] },
          "source": {"file":"recipes/default.rb","lines":[8,22]}  # file:line span for the declaration
        }
      ],
      "templates": [
        {
          "path": "/etc/httpd/conf/httpd.conf",      # resource "path" property (if present)
          "source": "templates/default/httpd.conf.erb",
          "vars": ["port","@server_admin","node['fqdn']"]     # variables(...), ERB @vars, and node[...] used in ERB
        }
      ]
    }
  ],
  "custom_resources": [
    {
      "name": "vhost",
      "file": "resources/vhost.rb",
      "provides": ["apache2_vhost"],                # provides :alias
      "properties": [
        {"name":"port","type":"Integer","default":null,"name_property":false,"required":false,"extra_kwargs":null}
      ],
      "actions": [
        {
          "name":"create",
          "source":{"file":"resources/vhost.rb","lines":[12,88]},
          "resources":[ /* same schema as recipe resources; templates here are enriched too */ ]
        }
      ],
      "attributes_read": ["node['apache2']['dir']"]
    }
  ],
  "meta": {
    "extractor_version": "1.3.0",
    "coverage": {
      "files_scanned": 17,
      "recipe_files": 11,
      "custom_resource_files": 6,
      "recipes": 11,
      "resources_total": 21,
      "custom_resources": 39,
      "properties_total": 203,
      "templates_total": 13,
      "dynamic_includes_total": 3,
      "unknown_names_without_expr": 0,      # should be 0 in healthy runs
      "notes": [
        "Templates may be declared inside custom-resource actions; recipe-level count can be 0 and still be OK.",
        "Dynamic includes recorded under includes_dynamic; targets are runtime-computed."
      ]
    }
  }
}
===============================================================================

NOTES
- The schema is intentionally additive: new fields (e.g., meta.coverage) do not break
  downstream consumers that ignore unknown keys.
- We focus on *deterministic extraction* of "facts" with file:line citations. No LLM needed.
"""

import json
import os
import re
import glob
from typing import Dict, List, Optional, Any, Tuple

# ---------------- Tree-sitter bootstrap ----------------
from tree_sitter import Parser


def _make_ruby_parser() -> Parser:
    """
    Initialize a Ruby parser across both the newer and classic tree_sitter_languages APIs.

    Returns
    -------
    Parser
        A configured Tree-sitter Parser for Ruby.

    Raises
    ------
    RuntimeError
        If neither API path is available (suggests actionable pip install).
    """
    # Prefer newer convenience API (bundles parser + language setup)
    try:
        from tree_sitter_languages import get_parser  # type: ignore
        return get_parser("ruby")
    except Exception:
        pass

    # Fallback: classic API (explicitly get Language and set on Parser)
    try:
        from tree_sitter_languages import get_language  # type: ignore
        p = Parser()
        p.set_language(get_language("ruby"))
        return p
    except Exception as e:
        raise RuntimeError(
            "Could not initialize a Ruby parser. Try one of:\n"
            "  pip install 'tree_sitter==0.20.4' 'tree_sitter_languages==1.10.2'\n"
            "  OR pip install --upgrade tree_sitter tree_sitter_languages\n"
            f"Original error: {e}"
        )


PARSER = _make_ruby_parser()

# ---------------- Domain constants ----------------

# Known Chef resource types (non-exhaustive but broad). Add more as needed.
RESOURCE_TYPES = {
    # Core
    "package", "service", "template", "file", "directory", "user", "group", "execute",
    "remote_file", "cookbook_file", "bash", "cron", "link", "mount", "git", "ruby_block",
    # Extras / platform-specific
    "apt_package", "yum_package", "dnf_package", "zypper_package", "homebrew_package", "windows_package",
    "windows_service", "systemd_unit", "launchd", "powershell_script", "script",
    "apt_update", "yum_repository", "apt_repository", "chocolatey_package", "dsc_resource",
}

# Property names we treat as "likely" in resource blocks (helps us avoid confusing
# nested resource calls with properties when scanning inside a block).
PROPERTY_KEYS_HINT = {
    "path", "source", "owner", "group", "mode", "variables", "cookbook", "content",
    "recursive", "provider", "retries", "retry_delay", "sensitive", "command",
    "only_if", "not_if", "environment", "creates", "cwd", "user", "backup",
}

# ---------------- Small helpers ----------------

def read_bytes(path: str) -> bytes:
    """Read a file as bytes (Tree-sitter needs byte offsets)."""
    with open(path, "rb") as f:
        return f.read()


def read_text(path: str) -> str:
    """Read a file as text with forgiving decoding (for ERB scanning)."""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def node_text(src: bytes, node) -> str:
    """Return textual slice of `src` corresponding to Tree-sitter node."""
    return src[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")


def walk(node):
    """
    Iterative DFS over a Tree-sitter node (no recursion depth issues).

    Yields
    ------
    node
        Each descendant (preorder).
    """
    stack = [node]
    while stack:
        cur = stack.pop()
        yield cur
        for i in range(cur.child_count - 1, -1, -1):
            stack.append(cur.child(i))


def strip_quotes(s: str) -> str:
    """Strip leading/trailing quotes (single or double) from a string literal."""
    s = s.strip()
    if len(s) >= 2 and s[0] in "\"'" and s[-1] == s[0]:
        return s[1:-1]
    return s


def relpath(path: str, root: str) -> str:
    """Return a stable relative path (fallback to basename if relpath fails)."""
    try:
        return os.path.relpath(path, root)
    except Exception:
        return os.path.basename(path)

# ---------------- Attribute + ERB scanning ----------------

# Matches node['a']['b'] chains in Ruby code or ERB (we reuse it).
ATTR_RE = re.compile(r"node\[(?:'|\")([^'\"]+)(?:'|\")\](?:\[(?:'|\")([^'\"]+)(?:'|\")\])*")


def scan_attributes_in_text(text: str) -> List[str]:
    """
    Extract all node[...] attribute access chains from plain text.

    Examples
    --------
    "node['apache2']['dir']" -> ["node['apache2']['dir']"]

    Returns
    -------
    List[str]
        Sorted unique attribute chains.
    """
    out = set()
    for m in ATTR_RE.finditer(text):
        first = m.group(1)
        rest = [g for g in m.groups()[1:] if g]
        out.add("node['" + "']['".join([first] + rest) + "']")
    return sorted(out)


# ERB helper to capture node[...] when rendered inline like "<%= node['x']['y'] %>"
ERB_NODE_VAR_RE = re.compile(r"<%=\s*node\s*(\[(?:'|\")[^%]+(?:'|\")\])\s*%>", re.MULTILINE)


def scan_template_node_vars(erb_path: Optional[str]) -> List[str]:
    """
    Scan an ERB file for node[...] usage. Falls back to generic attr scan.

    Returns
    -------
    List[str]
        Sorted unique node[...] chains referenced in the ERB.
    """
    if not erb_path or not os.path.isfile(erb_path):
        return []
    txt = read_text(erb_path)
    found = set()
    for m in ERB_NODE_VAR_RE.finditer(txt):
        raw = m.group(1)
        keys = re.findall(r"(?:'|\")([^'\"]+)(?:'|\")", raw)
        if keys:
            found.add("node['" + "']['".join(keys) + "']")
    found |= set(scan_attributes_in_text(txt))  # also catch node[...] in non-ERB contexts
    return sorted(found)


# ERB instance variables: @var_name
ERB_INSTANCE_VAR_RE = re.compile(r"@([A-Za-z_]\w*)")


def scan_template_instance_vars(erb_path: Optional[str]) -> List[str]:
    """
    Scan ERB for @instance variables.

    Returns
    -------
    List[str]
        Sorted unique instance variable names (without '@').
    """
    if not erb_path or not os.path.isfile(erb_path):
        return []
    txt = read_text(erb_path)
    return sorted(set(ERB_INSTANCE_VAR_RE.findall(txt)))

# ---------------- include_recipe scanners ----------------
# We split into static includes vs dynamic includes.
#   - static: include_recipe 'cookbook::recipe'  OR  include_recipe :symbol
#   - dynamic: anything with interpolation '#{...}', variables, concatenation,
#              or unrecognized argument shapes.

INCLUDE_STR_RE = re.compile(r"""include_recipe\s*\(\s*(['"])(?P<val>[^'"]+)\1\s*\)""")
INCLUDE_STR_BARE_RE = re.compile(r"""include_recipe\s+(['"])(?P<val>[^'"]+)\1""")
INCLUDE_SYM_RE = re.compile(r"""include_recipe\s*\(\s*:(?P<sym>\w+)\s*\)""")
INCLUDE_SYM_BARE_RE = re.compile(r"""include_recipe\s+:(?P<sym>\w+)""")


def scan_includes_split(text: str) -> Tuple[List[str], List[str]]:
    """
    Detect include_recipe calls and classify into (static, dynamic).

    Parameters
    ----------
    text : str
        Source code of a recipe file.

    Returns
    -------
    (List[str], List[str])
        Tuple of (includes, includes_dynamic).
    """
    includes: List[str] = []
    includes_dyn: List[str] = []

    # 1) Simple literal strings (with or without parens)
    for rx in (INCLUDE_STR_RE, INCLUDE_STR_BARE_RE):
        for m in rx.finditer(text):
            val = m.group("val")
            if "#{" in val:
                includes_dyn.append(val)
            else:
                includes.append(val)

    # 2) Symbols are static
    for rx in (INCLUDE_SYM_RE, INCLUDE_SYM_BARE_RE):
        for m in rx.finditer(text):
            includes.append(m.group("sym"))

    # 3) Anything else is likely dynamic (concat, vars, method calls)
    for line in text.splitlines():
        if "include_recipe" not in line:
            continue
        if (not INCLUDE_STR_RE.search(line)
            and not INCLUDE_STR_BARE_RE.search(line)
            and not INCLUDE_SYM_RE.search(line)
            and not INCLUDE_SYM_BARE_RE.search(line)):
            includes_dyn.append(line.strip())

    return sorted(set(includes)), sorted(set(includes_dyn))

# ---------------- File discovery ----------------

# We intentionally scan a handful of common cookbook layouts, including fixtures/examples.
SEARCH_RECIPE_GLOBS = [
    "recipes/*.rb",
    "test/cookbooks/*/recipes/*.rb",
    "spec/fixtures/cookbooks/*/recipes/*.rb",
    "test/fixtures/cookbooks/*/recipes/*.rb",
    "examples/**/recipes/*.rb",
    "examples/cookbooks/*/recipes/*.rb",
]


def find_recipe_files(cookbook_root: str) -> List[str]:
    """
    Find recipe Ruby files for a cookbook root.

    A "cookbook root" is a directory that contains metadata.rb and at least
    one of recipes/ or resources/.

    Returns
    -------
    List[str]
        Sorted unique absolute paths to recipe files.
    """
    files = []
    for pat in SEARCH_RECIPE_GLOBS:
        files.extend(glob.glob(os.path.join(cookbook_root, pat)))
    return sorted(set(files))


def find_custom_resource_files(cookbook_root: str) -> List[str]:
    """
    Find custom resource Ruby files (resources/*.rb) under a cookbook root.

    Returns
    -------
    List[str]
        Sorted unique absolute paths to custom resource files.
    """
    return sorted(set(glob.glob(os.path.join(cookbook_root, "resources", "*.rb"))))

# ---------------- AST utilities ----------------

def get_method_identifier(src: bytes, call_or_cmd) -> Optional[str]:
    """
    Extract the method identifier from a Tree-sitter 'call' or 'command' node.

    We look first for the 'method' field; if absent, we scan child identifiers.

    Returns
    -------
    Optional[str]
        The method name, e.g., 'template', 'service', 'action'.
    """
    ident = call_or_cmd.child_by_field_name("method")
    if ident:
        return node_text(src, ident)
    for ch in call_or_cmd.children:
        if ch.type == "identifier":
            return node_text(src, ch)
    return None


def arglist_node(call_or_cmd):
    """Return the arguments node (Tree-sitter field 'arguments') if present."""
    return call_or_cmd.child_by_field_name("arguments")


def arglist_text(src: bytes, call_or_cmd) -> str:
    """Return text of the arguments list, or empty string if absent."""
    args = arglist_node(call_or_cmd)
    return node_text(src, args) if args else ""


def _yield_in_order_no_keywords(node):
    """
    Yield child nodes in argument order, stopping before keyword/hash args.

    Tree-sitter represents args as a sequence; we stop when we hit a hash (keyword args),
    because positional args end there in Ruby syntax.
    """
    for ch in node.children:
        t = ch.type
        if t in ("hash", "bare_assoc_hash", "pair"):
            return
        if t != ",":
            yield ch


def iter_positional_args(src: bytes, call_or_cmd):
    """
    Iterate over positional-argument nodes for both "command" style and "call(...)" style.

    This normalizes the two Ruby call forms so downstream logic doesn't care.
    """
    args = arglist_node(call_or_cmd)
    if not args:
        # Command form (no parentheses); scan the call node itself.
        for ch in _yield_in_order_no_keywords(call_or_cmd):
            if ch == call_or_cmd.child_by_field_name("method"):
                continue
            if ch.type in ("argument_list", "parenthesized_arguments"):
                for sub in _yield_in_order_no_keywords(ch):
                    yield sub
            else:
                yield ch
        return
    # Call form with an argument list node.
    for ch in _yield_in_order_no_keywords(args):
        if ch.type in ("argument_list", "parenthesized_arguments"):
            for sub in _yield_in_order_no_keywords(ch):
                yield sub
        else:
            yield ch


def _symbol_or_string_value(src: bytes, node) -> Optional[str]:
    """Return the literal value if `node` is a symbol or string; else None."""
    t = node.type
    if t in ("string", "string_literal"):
        return strip_quotes(node_text(src, node))
    if t in ("symbol", "symbol_literal"):
        return node_text(src, node).lstrip(":").strip()
    return None


def first_arg_string_or_symbol(src: bytes, call_or_cmd) -> Optional[str]:
    """Return the first positional arg if it is a literal string/symbol; else None."""
    for n in iter_positional_args(src, call_or_cmd):
        val = _symbol_or_string_value(src, n)
        if val is not None:
            return val
    return None


def first_arg_node(src: bytes, call_or_cmd):
    """Return the node of the first positional arg (any type), or None."""
    for n in iter_positional_args(src, call_or_cmd):
        return n
    return None


def constantish_text(src: bytes, node) -> Optional[str]:
    """Return textual constant/identifier/scope_resolution tokens as a string."""
    if node.type in ("constant", "identifier", "scope_resolution"):
        return node_text(src, node).strip()
    return None

# ---------------- kw-args (hash) parsing ----------------

def kw_pairs_from_args(src: bytes, call_or_cmd) -> Dict[str, str]:
    """
    Parse keyword arguments from a call/command node into a dict of {key: value_text}.

    We support labels (foo:), symbols (:foo), strings ("foo"), and identifiers as keys.
    Values are preserved as raw text where not a simple literal (e.g., arrays/consts).

    NOTE: We do NOT execute Ruby; this is a static, best-effort parse.
    """
    result: Dict[str, str] = {}
    args = arglist_node(call_or_cmd)
    if not args:
        return result
    for ch in args.children:
        if ch.type not in ("hash", "bare_assoc_hash"):
            continue
        for p in ch.children:
            if p.type != "pair":
                continue
            key_node = p.child_by_field_name("key")
            val_node = p.child_by_field_name("value")
            if not key_node:
                continue
            # Key formats: label, symbol, string, identifier
            if key_node.type == "label":
                key = node_text(src, key_node).rstrip(":").strip()
            elif key_node.type in ("symbol", "symbol_literal", "string", "string_literal", "identifier"):
                key = strip_quotes(node_text(src, key_node)).lstrip(":")
            else:
                key = node_text(src, key_node).strip()
            # Value: keep as text unless simple literal
            val = None
            if val_node:
                vt = val_node.type
                raw = node_text(src, val_node).strip()
                if raw in ("true", "false", "nil"):
                    val = raw
                elif vt in ("string", "string_literal"):
                    val = strip_quotes(raw)
                elif vt in ("symbol", "symbol_literal"):
                    val = raw.lstrip(":")
                else:
                    val = raw
            result[key] = val
    return result

# ---------------- Recipe resource parsing ----------------

# notifies/subscribes are often written as: notifies :restart, "service[nginx]", :delayed
NOTIFY_RE = re.compile(
    r"^\s*(?::)?(?P<action>\w+)\s*,\s*[\"'](?P<target>[^\"']+)[\"']\s*(?:,\s*:(?P<timing>\w+))?",
    re.DOTALL
)


def parse_block_properties(src: bytes, block_node, recipe_relfile: str):
    """
    Parse the *inside* of a resource block for actions, guards, notifications, and properties.

    We treat nested calls inside the block as "properties" unless they match a known resource
    type (we do not recurse nested resources here). Special handling:
      - action :create  => actions[]
      - only_if/not_if => guards[]
      - notifies/subscribes => parsed (with file:line citation)
      - variables(...) => capture keys from the hash (used in template enrichment)
    """
    actions, guards, notifies, subscribes = [], [], [], []
    props: Dict[str, List[str]] = {}

    if block_node is None or block_node.type != "block":
        return actions, guards, notifies, subscribes, props

    body = block_node.child_by_field_name("body")
    # Some grammars place statements directly as siblings; guard against both layouts.
    body_nodes = [body] if body else [ch for ch in block_node.children if ch is not block_node.child_by_field_name("call")]

    def add_prop(k: str, v: str):
        props.setdefault(k, [])
        if v not in props[k]:
            props[k].append(v)

    def add_prop_list(k: str, values: List[str]):
        if not values:
            return
        props.setdefault(k, [])
        for v in values:
            if v not in props[k]:
                props[k].append(v)

    for b in body_nodes:
        for n in walk(b):
            if n.type not in ("call", "command"):
                continue
            meth = get_method_identifier(src, n)
            if not meth:
                continue

            if meth == "action":
                # action :create or action "create"
                txt = arglist_text(src, n)
                vals = re.findall(r":(\w+)|['\"]([^'\"]+)['\"]", txt)
                for sym, s in vals:
                    actions.append(sym or s)
                continue

            if meth in ("only_if", "not_if"):
                # Guards often take a shell command or Ruby block; we capture the text.
                txt = arglist_text(src, n).strip() or "<ruby_block_guard>"
                guards.append({"type": meth, "expr": txt})
                continue

            if meth in ("notifies", "subscribes"):
                # We parse the common pattern; for exotic forms we still cite file:line.
                txt = arglist_text(src, n)
                m = NOTIFY_RE.search(txt)
                if m:
                    entry = {
                        "action": m.group("action"),
                        "target": m.group("target"),
                        "timing": m.group("timing") or "delayed",
                        "source": {"file": recipe_relfile, "lines": [n.start_point[0] + 1, n.end_point[0] + 1]},
                    }
                    (notifies if meth == "notifies" else subscribes).append(entry)
                continue

            if meth == "variables":
                # Capture keys from variables(...) hashes — crucial for template var discovery.
                args = n.child_by_field_name("arguments")
                if args:
                    var_keys = []
                    for ch in args.children:
                        if ch.type in ("hash", "bare_assoc_hash"):
                            for p in ch.children:
                                if p.type != "pair":
                                    continue
                                key_node = p.child_by_field_name("key")
                                if not key_node:
                                    continue
                                if key_node.type == "label":
                                    var_keys.append(node_text(src, key_node).rstrip(":").strip())
                                elif key_node.type in ("symbol", "symbol_literal", "string", "string_literal", "identifier"):
                                    var_keys.append(strip_quotes(node_text(src, key_node)).lstrip(":"))
                                else:
                                    var_keys.append(node_text(src, key_node).strip())
                    add_prop_list("variables_keys", sorted(set(var_keys)))
                # Also store a lightweight textual hint for variables(...) arg
                txt = arglist_text(src, n).strip()
                if txt:
                    add_prop(meth, txt.split(",")[0].strip().strip('"\''))
                continue

            # Generic property capture — but only if it's not itself a resource type.
            txt = arglist_text(src, n).strip()
            if not txt:
                continue
            key = meth
            if (key in PROPERTY_KEYS_HINT) or (key not in RESOURCE_TYPES):
                val = strip_quotes(txt.split(",")[0])
                add_prop(key, val)

    return [str(a) for a in actions], guards, notifies, subscribes, props


def find_recipe_resources(src: bytes, tree, recipe_relfile: str) -> List[Dict[str, Any]]:
    """
    Parse a recipe AST and return Chef resources declared in it.

    We detect:
      1) Block-form resources:   package 'httpd' do ... end
      2) One-liners (commands):  service 'httpd'

    For each resource we extract:
      - type (package/service/template/...)
      - literal title (name) or the raw expression (name_expr) if non-literal
      - actions, guards, notifies, subscribes
      - properties (keyed by method calls inside the block)
      - file:line citation
    """
    resources: List[Dict[str, Any]] = []
    seen_block_heads = set()
    root = tree.root_node

    # PASS 1: block-form resources
    for n in walk(root):
        if n.type != "block":
            continue
        call = n.child_by_field_name("call") or (n.child(0) if n.child_count > 0 else None)
        if not call:
            continue
        method = get_method_identifier(src, call)
        if not method or method not in RESOURCE_TYPES:
            continue

        # Resource title: keep literal in 'name', else preserve raw in 'name_expr'
        name = first_arg_string_or_symbol(src, call)
        name_expr = None
        if name is None:
            first_node = first_arg_node(src, call)
            if first_node is not None:
                name_expr = node_text(src, first_node).strip()

        rid = f"{method}[{(name or name_expr or '?')}]"
        start_line = call.start_point[0] + 1
        end_line = n.end_point[0] + 1

        actions, guards, notifies, subscribes, props = parse_block_properties(src, n, recipe_relfile)

        resources.append({
            "rid": rid,
            "type": method,
            "name": name,
            "name_expr": name_expr,
            "actions": actions or [],
            "guards": guards,
            "notifies": notifies,
            "subscribes": subscribes,
            "properties": props,
            "source": {"file": recipe_relfile, "lines": [start_line, end_line]},
        })
        seen_block_heads.add((call.start_byte, call.end_byte))

    # PASS 2: one-liner resources (avoid double-counting heads we saw as blocks)
    for n in walk(root):
        method = get_method_identifier(src, n)
        if not method or method not in RESOURCE_TYPES:
            continue
        parent = n.parent
        if parent is not None and parent.type == "block":
            if (n.start_byte, n.end_byte) in seen_block_heads:
                continue

        name = first_arg_string_or_symbol(src, n)
        name_expr = None
        if name is None:
            first_node = first_arg_node(src, n)
            if first_node is not None:
                name_expr = node_text(src, first_node).strip()

        rid = f"{method}[{(name or name_expr or '?')}]"
        line = n.start_point[0] + 1

        resources.append({
            "rid": rid,
            "type": method,
            "name": name,
            "name_expr": name_expr,
            "actions": [],
            "guards": [],
            "notifies": [],
            "subscribes": [],
            "properties": {},
            "source": {"file": recipe_relfile, "lines": [line, line]},
        })

    return resources

# ---------------- Template resolution + enrichment ----------------

def resolve_template_source(cookbook_root: str, template_source: Optional[str]) -> Optional[str]:
    """
    Resolve a template resource's 'source' (or infer from 'path') to a concrete ERB path.

    We search templates/**/<source> and templates/<source> within the cookbook.
    """
    if not template_source:
        return None
    patterns = [
        os.path.join(cookbook_root, "templates", "**", template_source),
        os.path.join(cookbook_root, "templates", template_source),
    ]
    for pat in patterns:
        for c in glob.glob(pat, recursive=True):
            if os.path.isfile(c):
                return c
    return None


def enrich_template_resource(cookbook_root: str, r: Dict[str, Any]):
    """
    If a resource is 'template', attach:
      - r['template']['source'] : resolved ERB path (relative to root) or original source name
      - r['template']['vars']   : combined vars from:
          * variables(...) hash keys
          * ERB @instance_vars
          * node[...] usages inside ERB
    """
    if r.get("type") != "template":
        return
    props = r.get("properties", {}) or {}
    src_vals = props.get("source", [])
    src_name = src_vals[0] if src_vals else None
    if not src_name:
        path_vals = props.get("path", [])
        if path_vals:
            src_name = os.path.basename(path_vals[0])
    erb_path = resolve_template_source(cookbook_root, src_name)

    node_vars = scan_template_node_vars(erb_path) if erb_path else []
    inst_vars = scan_template_instance_vars(erb_path) if erb_path else []
    var_keys = props.get("variables_keys", [])

    r.setdefault("template", {})
    r["template"]["source"] = relpath(erb_path, cookbook_root) if erb_path else src_name
    combined = []
    combined.extend(sorted(set(var_keys)))
    combined.extend(["@" + v for v in inst_vars if v])
    combined.extend(v for v in node_vars if v)
    r["template"]["vars"] = sorted(set(combined))


def enrich_templates_in_resource_list(cookbook_root: str, resources: List[Dict[str, Any]]):
    """
    Apply template enrichment to every resource in a list (recipes or action blocks).
    """
    for r in resources:
        enrich_template_resource(cookbook_root, r)

# ---------------- Custom resources parsing ----------------

# Fallback regex to capture property name from raw arg text when AST layout is unusual
FALLBACK_NAME_RE = re.compile(
    r"""^\s*\(?\s*(?:
           :(?P<sym>[a-zA-Z_]\w*) |
           "(?P<dqs>[^"]+)" |
           '(?P<sqs>[^']+)'
        )""",
    re.VERBOSE,
)


def parse_property_call(src: bytes, n) -> Dict[str, Any]:
    """
    Parse a custom-resource `property(...)` declaration.

    Returns
    -------
    Dict[str, Any]
        {name, type, default, name_property, required, extra_kwargs}
    """
    name: Optional[str] = None
    ptype: Optional[str] = None

    pos = list(iter_positional_args(src, n))
    if pos:
        name = _symbol_or_string_value(src, pos[0])
    if name is None:
        # Some AST shapes make first arg tricky; fall back to regex on raw arg text.
        raw = arglist_text(src, n)
        m = FALLBACK_NAME_RE.search(raw or "")
        if m:
            name = m.group("sym") or m.group("dqs") or m.group("sqs")

    # Second positional arg often conveys type (e.g., Integer, [String, NilClass])
    if len(pos) >= 2:
        second = pos[1]
        st = second.type
        if st == "array":
            items = []
            for ch in second.children:
                if ch.type in ("constant", "identifier", "scope_resolution"):
                    items.append(node_text(src, ch).strip())
            ptype = "[" + ", ".join(items) + "]" if items else node_text(src, second).strip()
        elif st in ("constant", "identifier", "scope_resolution"):
            ptype = node_text(src, second).strip()
        else:
            ptype = node_text(src, second).strip()

    kwargs = kw_pairs_from_args(src, n)
    default = kwargs.get("default")
    name_property = kwargs.get("name_property", "false") == "true"
    required = kwargs.get("required", "false") == "true"
    if not ptype and "kind_of" in kwargs:
        ptype = kwargs["kind_of"]

    extra_kwargs = {k: v for k, v in kwargs.items()
                    if k not in ("default", "name_property", "required", "kind_of")}

    return {
        "name": name,
        "type": ptype,
        "default": default,
        "name_property": name_property,
        "required": required,
        "extra_kwargs": extra_kwargs or None
    }


def parse_custom_resource(src: bytes, tree, file_rel: str, cookbook_root: str, logical_name: str) -> Dict[str, Any]:
    """
    Parse a single custom resource file (resources/*.rb).

    Extracts:
      - provides aliases
      - properties (name/type/default/required/name_property)
      - actions :X do ... end  (with embedded resources parsed and templates enriched)
      - node[...] attribute reads in file
    """
    provides: List[str] = []
    properties: List[Dict[str, Any]] = []
    actions: List[Dict[str, Any]] = []

    text = src.decode("utf-8", errors="ignore")
    attr_reads = scan_attributes_in_text(text)

    # provides :alias
    for n in walk(tree.root_node):
        if n.type not in ("call", "command"):
            continue
        meth = get_method_identifier(src, n)
        if meth == "provides":
            alias = first_arg_string_or_symbol(src, n)
            if alias:
                provides.append(alias)

    # property(...)
    for n in walk(tree.root_node):
        if n.type not in ("call", "command"):
            continue
        meth = get_method_identifier(src, n)
        if meth != "property":
            continue
        prop = parse_property_call(src, n)
        properties.append(prop)

    # action :X do ... end
    for n in walk(tree.root_node):
        if n.type != "block":
            continue
        call = n.child_by_field_name("call") or (n.child(0) if n.child_count > 0 else None)
        if not call:
            continue
        meth = get_method_identifier(src, call)
        if meth != "action":
            continue
        action_name = first_arg_string_or_symbol(src, call) or "unknown"

        # Parse resources inside the action block as if it were a recipe
        class _FakeTree:
            def __init__(self, root): self.root_node = root
        nested_resources = find_recipe_resources(src, _FakeTree(n), file_rel)
        enrich_templates_in_resource_list(cookbook_root, nested_resources)

        actions.append({
            "name": action_name,
            "source": {"file": file_rel, "lines": [call.start_point[0] + 1, n.end_point[0] + 1]},
            "resources": nested_resources
        })

    return {
        "name": logical_name,
        "file": file_rel,
        "provides": sorted(set(provides)),
        "properties": properties,
        "actions": actions,
        "attributes_read": attr_reads
    }

# ---------------- Top-level extract ----------------

def _coverage_from_payload(cookbook_root: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a coverage summary from the extracted payload.

    Returns
    -------
    Dict[str, Any]
        Counts and small notes that explain what we covered, helping users
        understand "low output" cases (e.g., no top-level recipe templates).
    """
    recipes = payload.get("recipes", [])
    custom = payload.get("custom_resources", [])

    recipe_files = set(r.get("file") for r in recipes)
    cr_files = set(x.get("file") for x in custom)

    resources_total = sum(len(r.get("resources", [])) for r in recipes)
    properties_total = sum(len(x.get("properties", [])) for x in custom)
    templates_total = sum(1 for r in recipes for _t in r.get("templates", []))
    dynamic_includes_total = sum(len(r.get("includes_dynamic", []) or []) for r in recipes)
    unknown_names_without_expr = sum(
        1
        for r in recipes
        for res in r.get("resources", [])
        if (res.get("name") in (None, "?")) and not res.get("name_expr")
    )

    # Compose helpful notes (kept short; expand if needed)
    notes = []
    if templates_total == 0 and any(cr.get("actions") for cr in custom):
        notes.append("Templates may be declared inside custom-resource actions; recipe-level count can be 0.")
    if dynamic_includes_total > 0:
        notes.append("Dynamic includes recorded under includes_dynamic; targets are runtime-computed.")
    if unknown_names_without_expr == 0:
        notes.append("All non-literal resource titles have name_expr preserved.")

    # Compute a rough file count (recipes + custom resources + metadata.rb if present)
    files_scanned = len(recipe_files) + len(cr_files)
    meta_file = os.path.join(cookbook_root, "metadata.rb")
    if os.path.exists(meta_file):
        files_scanned += 1

    return {
        "files_scanned": files_scanned,
        "recipe_files": len(recipe_files),
        "custom_resource_files": len(cr_files),
        "recipes": len(recipes),
        "resources_total": resources_total,
        "custom_resources": len(custom),
        "properties_total": properties_total,
        "templates_total": templates_total,
        "dynamic_includes_total": dynamic_includes_total,
        "unknown_names_without_expr": unknown_names_without_expr,
        "notes": notes or None,
    }


def extract_chef_facts_comprehensive(cookbook_root: str) -> Dict[str, Any]:
    """
    Extract facts from a single cookbook root.

    A cookbook root is expected to contain metadata.rb and at least one of:
    recipes/ or resources/.

    Returns
    -------
    Dict[str, Any]
        The full payload per the schema: recipes, custom_resources, and meta.coverage.
    """
    # Use normpath instead of abspath to avoid blocking os.getcwd() call
    cookbook_root = os.path.normpath(cookbook_root)

    # ---- Recipes
    recipes_out: List[Dict[str, Any]] = []
    for rf in find_recipe_files(cookbook_root):
        src = read_bytes(rf)
        tree = PARSER.parse(src)
        recipe_rel = relpath(rf, cookbook_root)

        resources = find_recipe_resources(src, tree, recipe_rel)
        enrich_templates_in_resource_list(cookbook_root, resources)

        text = src.decode("utf-8", errors="ignore")
        attrs = scan_attributes_in_text(text)
        includes, includes_dyn = scan_includes_split(text)

        recipes_out.append({
            "name": os.path.splitext(os.path.basename(rf))[0],
            "file": recipe_rel,
            "includes": includes,
            "includes_dynamic": includes_dyn,
            "resources": resources,
            "attributes_read": attrs,
            "templates": [
                {
                    "path": r.get("properties", {}).get("path", [None])[0],
                    "source": (r.get("template") or {}).get("source"),
                    "vars": (r.get("template") or {}).get("vars", []),
                }
                for r in resources if r["type"] == "template"
            ],
        })

    # ---- Custom resources
    custom_out: List[Dict[str, Any]] = []
    for crf in find_custom_resource_files(cookbook_root):
        src = read_bytes(crf)
        tree = PARSER.parse(src)
        file_rel = relpath(crf, cookbook_root)
        logical_name = os.path.splitext(os.path.basename(crf))[0]
        custom_out.append(parse_custom_resource(src, tree, file_rel, cookbook_root, logical_name))

    # Build payload and attach coverage metadata
    payload: Dict[str, Any] = {
        "schema": "chef-facts@1",
        "cookbook": os.path.basename(cookbook_root),
        "recipes": recipes_out,
        "custom_resources": custom_out,
        "meta": {
            "extractor_version": "1.3.0",
            "coverage": _coverage_from_payload(cookbook_root, {
                "recipes": recipes_out,
                "custom_resources": custom_out
            }),
        },
    }
    return payload


# ---------------- Alias for compatibility ----------------
def extract(cookbook_root: str) -> Dict[str, Any]:
    """Alias for extract_chef_facts_comprehensive for compatibility."""
    return extract_chef_facts_comprehensive(cookbook_root)
