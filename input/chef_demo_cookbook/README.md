# Nginx Webapp Cookbook

A comprehensive Chef cookbook for deploying and configuring Nginx web server with webapp support.

## Requirements

- **Chef**: >= 15.3
- **Ruby**: >= 2.6
- **Platforms**: Ubuntu 18.04+, CentOS 7+

## Features

- Modern Chef 15+ patterns with unified_mode
- SSL/HTTPS support with automatic certificate generation
- Firewall integration
- Performance optimizations
- Security hardening
- Monitoring integration
- Platform-specific configurations

## Usage

Include `nginx-webapp` in your node's `run_list`:

```json
{
  "run_list": [
    "recipe[nginx-webapp]"
  ]
}
```

## Testing the Chef Analysis Agent

This cookbook is designed to test various aspects of Chef cookbook analysis:

### Expected Analysis Results

- **Min Chef Version**: 15.3 (from metadata.rb chef_version requirement)
- **Migration Effort**: MEDIUM (multiple resources, templates, complex logic)
- **Primary Purpose**: "Nginx web server configuration"
- **Services**: ["nginx"]
- **Packages**: ["nginx"]
- **Dependencies**: ["compat_resource", "systemd", "firewall"]
- **Is Wrapper**: false (contains own resources, not just include_recipe)
- **Reusability**: HIGH (well-structured, configurable)

### Test Cases Covered

1. **Version Detection**: Chef 15+ features (unified_mode)
2. **Complexity Analysis**: Multiple resource types, templates, libraries
3. **Technology Detection**: Nginx-specific patterns
4. **Dependency Analysis**: Direct dependencies in metadata.rb
5. **File Management**: Templates and static files
6. **Service Management**: Nginx service configuration
7. **Security Features**: SSL, firewall, security headers

## License

Apache-2.0
