# X2A API - Multi-Agent Infrastructure Automation Platform

## Overview

The X2A API is a comprehensive FastAPI application that provides AI-powered agents for infrastructure automation tasks. The platform hosts multiple specialized agents that handle different aspects of infrastructure management, migration, and automation. Each agent leverages LlamaStack for AI-powered analysis, with some agents utilizing Retrieval-Augmented Generation (RAG) for enhanced context and knowledge integration.


## How to use 

### Streaming Agent API Examples

All endpoints support Server-Sent Events (SSE).
Each response emits events in real time, perfect for UI feedback and automation.




### 1. Chef Cookbook Analysis (Streaming)

**POST** `/chef/analyze/stream`

```bash
curl -N -X POST http://localhost:8000/chef/analyze/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "cookbook_name": "demo_cookbook",
    "files": {
      "metadata.rb": "name \"demo_cookbook\"\ndepends \"httpd\"",
      "recipes/default.rb": "package \"httpd\" do\n  action :install\nend\nservice \"httpd\" do\n  action [:enable, :start]\nend"
    }
  }'
```

**Example Streamed Response**

```text
data: {"type": "progress", "status": "processing", "message": "Chef cookbook analysis started"}

data: {"type": "final_analysis", "data": { "success": true, "cookbook_name": "demo_cookbook", ... }, "correlation_id": "a9e60266"}
```

---

### 2. Query Context (Streaming)

**POST** `/context/query/stream`

```bash
curl -N -X POST http://localhost:8000/context/query/stream \
  -H "Content-Type: application/json" \
  -d '{
    "code": "nginx",
    "top_k": 3
  }'
```

**Example Streamed Response**

```text
data: {"event": "start", "timestamp": "2025-06-06T02:28:59Z", "msg": "Context search started"}

data: {"event": "progress", "progress": 0.5, "msg": "Searching knowledge base...", "timestamp": "2025-06-06T02:28:59Z"}

data: {"event": "result", "context": [
  { "text": "Result 1\nContent: # Puppet to Ansible File Management\n..." },
  { "text": "Result 2\nContent: # Chef to Ansible Package Installation\n..." },
  { "text": "Result 3\nContent: Chef to Ansible Conversion Guide\n..." }
], "elapsed_time": 19.60, "correlation_id": "fe99b4bf-0282-4392-b9ef-b703c03578dd", "timestamp": "2025-06-06T02:29:19Z", "processing_time": 19.91}
```

---

### 3. Generate Playbook (Streaming)

**POST** `/generate/playbook/stream`

```bash
curl -N -X POST http://localhost:8000/generate/playbook/stream \
  -H "Content-Type: application/json" \
  -d '{
    "input_code": "package { \"httpd\": ensure => present }",
    "context": "Convert this Puppet resource to Ansible"
  }'
```

**Example Streamed Response**

```text
data: {"event": "start", "timestamp": "2025-06-06T02:20:55Z", "msg": "Generation started"}

data: {"event": "progress", "progress": 0.5, "msg": "Generating playbook...", "timestamp": "2025-06-06T02:20:55Z"}

data: {"event": "result", "playbook": "---\n# This playbook installs the httpd package on a Linux system\n# It uses the Ansible package module to ensure the package is present\n\n- name: Install httpd package\n  hosts: all\n  become: yes\n\n  tasks:\n  - name: Install httpd package\n    package:\n      name: httpd\n      state: present\n", "timestamp": "2025-06-06T02:20:59Z", "processing_time": 4.95}
```

---



### 4. Validate Playbook (Streaming)

**POST** `/validate/playbook/stream`

```bash
curl -N -X POST http://localhost:8000/validate/playbook/stream \
  -H "Content-Type: application/json" \
  -d '{
    "playbook": "---\n- name: Hello World Playbook\n  hosts: localhost\n  tasks:\n    - name: Print hello message\n      debug:\n        msg: \"hello world!\"",
    "profile": "basic"
  }'
```

**Example Streamed Response**

```text
data: {"event": "start", "timestamp": "2025-06-06T02:17:01Z", "msg": "Validation started"}

data: {"event": "progress", "progress": 0.5, "msg": "Agent analyzing playbook with tool...", "timestamp": "2025-06-06T02:17:01Z"}

data: {"event": "result", "success": true, "validation_passed": false, "exit_code": 2, "message": "Playbook validation failed with 2 issue(s)", ... }
```

---

## Tips for Using Streaming Endpoints

* Use `curl -N` or a compatible HTTP client to see events as they arrive.
* Each event is delivered as a separate line:
  `data: { ... }`
* Parse each line as JSON for programmatic consumption or real-time UI updates.


## Architecture

### Platform Components

- **FastAPI Application**: Multi-agent REST API platform
- **Multi-Agent System**: Specialized agents for different automation tasks
- **Gunicorn/Uvicorn**: ASGI server for production deployment
- **LlamaStack Integration**: AI analysis engine for all agents
- **RAG System**: Knowledge retrieval for context augmentation
- **ConfigMap**: Centralized configuration management
- **Horizontal Pod Autoscaler**: Automatic scaling based on resource usage

### Container Image

The service is packaged as a container image using UBI 9 Python 3.11 base image and published to GitHub Container Registry:

```
ghcr.io/x2ansible/x2a-api:latest
```

## Multi-Agent Platform

The X2A API application hosts multiple specialized agents:

### Chef Analysis Agent (`/chef/*`)
Analyzes Chef cookbooks for version requirements, dependencies, and migration recommendations.

**Capabilities:**
- Version requirement analysis
- Dependency mapping and wrapper detection
- Migration effort estimation
- Consolidation recommendations

### Context Agent (`/context/*`)
Retrieves and analyzes infrastructure context using RAG to augment LLM responses with best practices and lessons learned.

**Capabilities:**
- Best practices retrieval from knowledge base
- Lessons learned integration via RAG
- Environment discovery and mapping
- Historical context and pattern analysis
- Configuration drift detection
- Infrastructure inventory management

**RAG Integration:**
- Retrieves relevant best practices from documentation repositories
- Augments responses with lessons learned from previous projects
- Provides context-aware recommendations based on historical data
- Integrates organizational knowledge and standards

### Generate Agent (`/generate/*`)
Generates automation code, configurations, and infrastructure definitions.

**Capabilities:**
- Ansible playbook generation
- Terraform configuration creation
- Kubernetes manifest generation
- Configuration template creation

### Validate Agent (`/validate/*`)
Validates automation code, configurations, and infrastructure definitions.

**Capabilities:**
- Syntax and structure validation
- Best practice compliance checking
- Security policy validation
- Resource constraint verification

### Deploy Agent (`/deploy/*`)
Manages deployment orchestration and automation execution.

**Capabilities:**
- Deployment plan creation
- Rollback strategy generation
- Environment promotion workflows
- Deployment status monitoring

## Common API Patterns

All agents follow consistent API patterns within the FastAPI application:

### Standard Endpoints (per agent)
- `GET /{agent}/health` - Agent health status
- `GET /{agent}/config` - Agent configuration
- `POST /{agent}/analyze` - Core analysis functionality
- `POST /{agent}/analyze/stream` - Streaming analysis with progress
- `POST /{agent}/analyze/upload` - File upload for analysis
- `POST /{agent}/analyze/upload/stream` - Streaming file upload analysis

### Common Response Structure
```json
{
  "success": true,
  "agent": "agent_name",
  "correlation_id": "unique_id",
  "metadata": {
    "agent_version": "1.0.0",
    "processing_time": 1.23,
    "model_used": "meta-llama/Llama-3.1-8B-Instruct",
    "rag_sources": ["best_practices_db", "lessons_learned"]
  },
  "results": {
    // Agent-specific analysis results
  }
}
```

## Agent-Specific Endpoints

### Chef Analysis Agent (`/chef`)

#### POST /chef/analyze
Analyze Chef cookbooks for version requirements and dependencies.

#### POST /chef/analyze/upload
Upload Chef cookbook files for analysis.

**Supported Files:**
- `metadata.rb` - Cookbook metadata and dependencies
- `recipes/*.rb` - Recipe files
- `attributes/*.rb` - Attribute files
- `templates/*` - Template files
- `libraries/*.rb` - Library files

### Context Agent (`/context`)

#### POST /context/discover
Discover and analyze infrastructure context with RAG-augmented best practices.

#### POST /context/best-practices
Retrieve best practices for specific technologies or scenarios using RAG.

#### POST /context/lessons-learned
Query lessons learned database for relevant historical insights.

#### POST /context/inventory
Generate infrastructure inventory from multiple sources.

#### POST /context/dependencies
Analyze cross-system dependencies with historical context.

**RAG-Enhanced Responses:**
All context agent endpoints augment LLM responses with retrieved knowledge:
- Best practices from documentation repositories
- Lessons learned from previous projects
- Organizational standards and guidelines
- Historical patterns and solutions

### Generate Agent (`/generate`)

#### POST /generate/ansible
Generate Ansible playbooks from requirements.

#### POST /generate/terraform
Generate Terraform configurations.

#### POST /generate/kubernetes
Generate Kubernetes manifests.

#### POST /generate/templates
Generate configuration templates.

### Validate Agent (`/validate`)

#### POST /validate/ansible
Validate Ansible playbooks and roles.

#### POST /validate/terraform
Validate Terraform configurations.

#### POST /validate/kubernetes
Validate Kubernetes manifests.

#### POST /validate/security
Perform security policy validation.

### Deploy Agent (`/deploy`)

#### POST /deploy/plan
Create deployment execution plans.

#### POST /deploy/execute
Execute deployment workflows.

#### POST /deploy/rollback
Generate rollback strategies.

#### POST /deploy/status
Monitor deployment status and progress.

## Platform Features

- **Multi-Agent Architecture**: Specialized agents for different automation tasks
- **FastAPI Native**: All agents hosted within single FastAPI application
- **RAG Integration**: Knowledge retrieval and augmentation for enhanced responses
- **File Upload Support**: Upload files directly through Swagger UI or API calls
- **Streaming Analysis**: Real-time progress updates via Server-Sent Events
- **Multiple Input Methods**: Support for JSON payloads, file uploads, and URL references
- **Cross-Agent Workflows**: Agents can collaborate on complex automation tasks
- **Health Monitoring**: Individual agent health checks and platform status
- **Auto-scaling**: Horizontal Pod Autoscaler for dynamic scaling
- **Resource Management**: CPU and memory limits with resource requests
- **Security**: Non-root container execution with security contexts

## Platform Configuration

### Agent Configuration Structure

Each agent can be configured with specific parameters:

```yaml
active_profile: "local"
defaults:
  llama_stack:
    base_url: "http://lss-chai.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com"
    model: "meta-llama/Llama-3.1-8B-Instruct"
  agents:
    chef_analysis:
      timeout: 120
      max_tokens: 4096
    context:
      timeout: 180
      max_tokens: 8192
      rag_enabled: true
      knowledge_sources:
        - "best_practices_db"
        - "lessons_learned_db"
        - "documentation_repo"
    generate:
      timeout: 300
      max_tokens: 16384
    validate:
      timeout: 90
      max_tokens: 4096
    deploy:
      timeout: 600
      max_tokens: 8192
```

### RAG Configuration for Context Agent

```yaml
context_agent:
  rag:
    enabled: true
    vector_store: "chromadb"
    embedding_model: "sentence-transformers/all-MiniLM-L6-v2"
    retrieval_top_k: 5
    knowledge_sources:
      best_practices:
        source_type: "documentation"
        path: "/knowledge/best-practices"
      lessons_learned:
        source_type: "database"
        connection_string: "postgresql://..."
      standards:
        source_type: "git_repo"
        repo_url: "https://github.com/org/standards"
```

### Environment Profiles
- **local**: Development configuration with shorter timeouts
- **staging**: Testing configuration with moderate resources
- **production**: Production configuration with extended timeouts and higher token limits

## Cross-Agent Workflows

The FastAPI application supports complex workflows that span multiple agents:

### Infrastructure Migration Workflow
1. **Context Agent**: Discover existing infrastructure + retrieve best practices via RAG
2. **Chef Analysis Agent**: Analyze current Chef configurations
3. **Generate Agent**: Create target Ansible playbooks
4. **Validate Agent**: Validate generated automation
5. **Deploy Agent**: Execute migration with monitoring

### Configuration Management Workflow
1. **Context Agent**: Inventory current configurations + lessons learned via RAG
2. **Validate Agent**: Check compliance and security
3. **Generate Agent**: Create standardized configurations
4. **Deploy Agent**: Apply configurations across environments

## Usage Examples

### Context Agent with RAG

```bash
# Get best practices for Ansible development
curl -X 'POST' \
  'https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/context/best-practices' \
  -H 'Content-Type: application/json' \
  -d '{
    "technology": "ansible",
    "use_case": "web_server_deployment",
    "environment": "production"
  }'

# Query lessons learned for Chef to Ansible migration
curl -X 'POST' \
  'https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/context/lessons-learned' \
  -H 'Content-Type: application/json' \
  -d '{
    "migration_type": "chef_to_ansible",
    "components": ["web_servers", "databases"],
    "challenges": ["dependency_management", "rolling_updates"]
  }'
```

### Multi-Agent Workflow Example

```bash
# 1. Discover infrastructure context with RAG-enhanced insights
curl -X 'POST' \
  'https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/context/discover' \
  -H 'Content-Type: application/json' \
  -d '{"environment": "production", "scope": "web_tier"}'

# 2. Analyze existing Chef configurations
curl -X 'POST' \
  'https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/chef/analyze/upload' \
  -F 'cookbook_name=web-server' \
  -F 'files=@metadata.rb' \
  -F 'files=@recipes/default.rb'

# 3. Generate Ansible equivalent
curl -X 'POST' \
  'https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/generate/ansible' \
  -H 'Content-Type: application/json' \
  -d '{"source_type": "chef", "target_requirements": {...}}'

# 4. Validate generated playbook
curl -X 'POST' \
  'https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/validate/ansible' \
  -F 'files=@generated-playbook.yml'

# 5. Create deployment plan
curl -X 'POST' \
  'https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/deploy/plan' \
  -H 'Content-Type: application/json' \
  -d '{"playbooks": [...], "environments": ["staging", "production"]}'
```

### Platform Health Check

```bash
# Check application health
curl https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/health

# Check individual agents
curl https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/chef/health
curl https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/context/health
curl https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/generate/health
curl https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/validate/health
curl https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/deploy/health
```

## API Documentation

### Interactive Documentation

Access the complete API documentation with interactive testing:

```
https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/docs
```

### Agent-Specific Documentation

Each agent provides its own documentation section:
- `/docs#/chef-analysis` - Chef Analysis Agent endpoints
- `/docs#/context` - Context Agent endpoints with RAG capabilities
- `/docs#/generate` - Generate Agent endpoints
- `/docs#/validate` - Validate Agent endpoints
- `/docs#/deploy` - Deploy Agent endpoints

## Platform Configuration

### Agent Configuration Structure

Each agent can be configured with specific parameters:

```yaml
active_profile: "local"
defaults:
  llama_stack:
    base_url: "http://lss-chai.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com"
    model: "meta-llama/Llama-3.1-8B-Instruct"
  agents:
    chef_analysis:
      timeout: 120
      max_tokens: 4096
    context:
      timeout: 180
      max_tokens: 8192
    generate:
      timeout: 300
      max_tokens: 16384
    validate:
      timeout: 90
      max_tokens: 4096
    deploy:
      timeout: 600
      max_tokens: 8192
```

### Environment Profiles
- **local**: Development configuration with shorter timeouts
- **staging**: Testing configuration with moderate resources
- **production**: Production configuration with extended timeouts and higher token limits

## Cross-Agent Workflows

The platform supports complex workflows that span multiple agents:

### Infrastructure Migration Workflow
1. **Context Agent**: Discover existing infrastructure
2. **Chef Analysis Agent**: Analyze current Chef configurations
3. **Generate Agent**: Create target Ansible playbooks
4. **Validate Agent**: Validate generated automation
5. **Deploy Agent**: Execute migration with monitoring

### Configuration Management Workflow
1. **Context Agent**: Inventory current configurations
2. **Validate Agent**: Check compliance and security
3. **Generate Agent**: Create standardized configurations
4. **Deploy Agent**: Apply configurations across environments

## Usage Examples

### Multi-Agent Workflow Example

```bash
# 1. Discover infrastructure context
curl -X 'POST' \
  'https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/context/discover' \
  -H 'Content-Type: application/json' \
  -d '{"environment": "production", "scope": "web_tier"}'

# 2. Analyze existing Chef configurations
curl -X 'POST' \
  'https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/chef/analyze/upload' \
  -F 'cookbook_name=web-server' \
  -F 'files=@metadata.rb' \
  -F 'files=@recipes/default.rb'

# 3. Generate Ansible equivalent
curl -X 'POST' \
  'https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/generate/ansible' \
  -H 'Content-Type: application/json' \
  -d '{"source_type": "chef", "target_requirements": {...}}'

# 4. Validate generated playbook
curl -X 'POST' \
  'https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/validate/ansible' \
  -F 'files=@generated-playbook.yml'

# 5. Create deployment plan
curl -X 'POST' \
  'https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/deploy/plan' \
  -H 'Content-Type: application/json' \
  -d '{"playbooks": [...], "environments": ["staging", "production"]}'
```

### Platform Health Check

```bash
# Check all agent health
curl https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/health

# Check individual agents
curl https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/chef/health
curl https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/context/health
curl https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/generate/health
curl https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/validate/health
curl https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/deploy/health
```

## API Documentation

### Interactive Documentation

Access the complete API documentation with interactive testing:

```
https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/docs
```

### Agent-Specific Documentation

Each agent provides its own documentation section:
- `/docs#/chef-analysis` - Chef Analysis Agent endpoints
- `/docs#/context` - Context Agent endpoints  
- `/docs#/generate` - Generate Agent endpoints
- `/docs#/validate` - Validate Agent endpoints
- `/docs#/deploy` - Deploy Agent endpoints

## Analysis Output

The service returns structured analysis results including:

### Version Requirements
- **min_chef_version**: Minimum Chef version required
- **min_ruby_version**: Minimum Ruby version required
- **migration_effort**: Effort estimation (LOW/MEDIUM/HIGH)
- **estimated_hours**: Estimated migration hours
- **deprecated_features**: List of deprecated features found

### Dependencies
- **is_wrapper**: Whether the cookbook is a wrapper
- **wrapped_cookbooks**: List of cookbooks this wraps via include_recipe
- **direct_deps**: Direct dependencies from metadata.rb
- **runtime_deps**: Runtime dependencies from include_recipe calls
- **circular_risk**: Circular dependency risk assessment

### Functionality
- **primary_purpose**: Description of what the cookbook does
- **services**: List of services managed
- **packages**: List of packages installed
- **files_managed**: Key files and directories managed
- **reusability**: Reusability assessment (LOW/MEDIUM/HIGH)
- **customization_points**: Key customization areas

### Recommendations
- **consolidation_action**: Recommended action (REUSE/EXTEND/RECREATE)
- **rationale**: Explanation of recommendation
- **migration_priority**: Priority level (LOW/MEDIUM/HIGH/CRITICAL)
- **risk_factors**: Migration risks to consider

## Deployment

### Prerequisites

- Kubernetes or OpenShift cluster
- Namespace: `x2ansible`
- Access to GitHub Container Registry (public image)
- LlamaStack service running and accessible

### Quick Start

1. **Apply the deployment configuration:**
```bash
kubectl apply -f deployment.yaml
```

2. **Verify deployment:**
```bash
kubectl get pods -n x2ansible -l app=x2a-api
kubectl get svc -n x2ansible
kubectl get route -n x2ansible  # OpenShift only
```

3. **Check service health:**
```bash
curl https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/chef/health
```

### Configuration

The application uses a YAML configuration file mounted from a ConfigMap with the following sections:

#### Profiles
- **local**: Development configuration (90s timeout, 4096 tokens)
- **staging**: Staging configuration (120s timeout, 4096 tokens)
- **production**: Production configuration (180s timeout, 8192 tokens)

#### LlamaStack Configuration
- **base_url**: LlamaStack service endpoint
- **model**: AI model to use for analysis

#### Environment Variables
- `CONFIG_FILE`: Path to configuration YAML file
- `UPLOAD_DIR`: Directory for temporary file uploads
- `LLAMASTACK_URL`: Override for LlamaStack service URL
- `LOG_LEVEL`: Logging level (INFO, DEBUG, ERROR)
- `PYTHONUNBUFFERED`: Ensure immediate log output

### Resource Configuration

#### Resource Limits
- **CPU**: 500m limit, 250m request
- **Memory**: 1Gi limit, 512Mi request
- **Storage**: 1Gi temporary upload storage

#### Auto-scaling
- **Min Replicas**: 1
- **Max Replicas**: 5
- **CPU Target**: 70% utilization
- **Memory Target**: 80% utilization

#### Health Checks
- **Liveness Probe**: /chef/health endpoint, 30s initial delay
- **Readiness Probe**: /chef/health endpoint, 10s initial delay

## Usage Examples

### Using Swagger UI

1. Navigate to: `https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/docs`
2. Find the `/chef/analyze/upload` endpoint
3. Click "Try it out"
4. Enter cookbook name: `apache-cookbook`
5. Upload files: metadata.rb, recipes/default.rb, attributes/default.rb
6. Click "Execute"

### Using curl for File Upload

```bash
# Create test files
cat > metadata.rb << 'EOF'
name 'apache2'
version '8.5.0'
chef_version '>= 15.3'
depends 'compat_resource', '>= 12.16.3'
EOF

cat > default.rb << 'EOF'
package node['apache']['package_name'] do
  action :install
end

service 'apache2' do
  action [:enable, :start]
end
EOF

# Upload for analysis
curl -X 'POST' \
  'https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/chef/analyze/upload' \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'cookbook_name=apache-cookbook' \
  -F 'files=@metadata.rb' \
  -F 'files=@default.rb'
```

### Using curl for JSON Analysis

```bash
curl -X 'POST' \
  'https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/chef/analyze' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "cookbook_name": "nginx-cookbook",
    "files": {
      "metadata.rb": "name \"nginx\"\nversion \"1.0.0\"\nchef_version \">= 15.0\"",
      "recipes/default.rb": "package \"nginx\" do\n  action :install\nend\n\nservice \"nginx\" do\n  action [:enable, :start]\nend"
    }
  }'
```

### Streaming Analysis

```bash
curl -X 'POST' \
  'https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/chef/analyze/upload/stream' \
  -H 'accept: text/event-stream' \
  -H 'Content-Type: multipart/form-data' \
  -F 'cookbook_name=apache-cookbook' \
  -F 'files=@metadata.rb' \
  -F 'files=@default.rb' \
  --no-buffer
```

## Monitoring and Operations

### Health Monitoring

The service provides comprehensive health checking:

```bash
# Basic health check
curl https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/chef/health

# Configuration check
curl https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/chef/config

# LlamaStack connectivity
curl https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/chef/agents/info
```

### Kubernetes Operations

```bash
# Check pod status
kubectl get pods -n x2ansible -l app=x2a-api

# View logs
kubectl logs -n x2ansible deployment/x2a-api -f

# Check autoscaling status
kubectl get hpa -n x2ansible

# Scale manually if needed
kubectl scale deployment x2a-api -n x2ansible --replicas=3

# Check resource usage
kubectl top pods -n x2ansible -l app=x2a-api
```

### Troubleshooting

#### Common Issues

**Pod CrashLoopBackOff**
```bash
# Check logs for errors
kubectl logs -n x2ansible deployment/x2a-api

# Common causes:
# - Missing 'fire' dependency
# - LlamaStack connectivity issues
# - Configuration file format errors
```

**Service Unavailable (503)**
```bash
# Check health endpoint
curl -v https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/chef/health

# Check pod readiness
kubectl get pods -n x2ansible -l app=x2a-api -o wide
```

**Analysis Timeouts**
```bash
# Check LlamaStack connectivity
curl https://x2a-api-x2ansible.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/chef/agents/info

# Verify LlamaStack service is accessible
kubectl exec -n x2ansible deployment/x2a-api -- curl -v http://lss-chai.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/v1/agents
```

#### Performance Tuning

**Increase Resources**
```yaml
resources:
  requests:
    memory: "1Gi"
    cpu: "500m"
  limits:
    memory: "2Gi"
    cpu: "1000m"
```

**Adjust Timeouts**
Update the ConfigMap with longer timeouts:
```yaml
agents:
  chef_analysis:
    timeout: 300  # 5 minutes
```

**Scale Horizontally**
```bash
kubectl scale deployment x2a-api -n x2ansible --replicas=3
```

## Development and CI/CD

### Container Build

The service uses GitHub Actions for automated building:

1. **Trigger**: Push to main branch
2. **Build**: Podman with UBI 9 Python 3.11
3. **Dependencies**: Installed from requirements.txt
4. **Registry**: GitHub Container Registry (public)
5. **Labels**: OCI labels for package metadata

### Dependencies

Core Python dependencies:
- `fastapi`: Web framework
- `uvicorn[standard]`: ASGI server
- `gunicorn`: Process manager
- `llama-stack-client`: AI integration
- `httpx`: HTTP client
- `fire`: CLI tool compatibility
- `pydantic`: Data validation
- `python-multipart`: File upload support

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export CONFIG_FILE=config/config.yaml
export UPLOAD_DIR=/tmp/uploads
export LOG_LEVEL=DEBUG

# Run development server
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### Testing

```bash
# Health check
curl http://localhost:8000/chef/health

# File upload test
curl -X POST http://localhost:8000/chef/analyze/upload \
  -F 'cookbook_name=test' \
  -F 'files=@test-metadata.rb'

# Access Swagger UI
open http://localhost:8000/docs
```

## Security Considerations

### Container Security
- Runs as non-root user (UID 1001)
- Read-only root filesystem where possible
- Dropped ALL capabilities
- Security contexts applied at pod and container level

### Network Security
- TLS termination at edge (OpenShift Route)
- Internal communication over HTTP
- No sensitive data in environment variables

### File Upload Security
- File type validation (text files only)
- Size limits enforced
- Temporary storage with cleanup
- Input sanitization and validation

## Support and Contributing

### Getting Help
- Check the health endpoints for service status
- Review pod logs for detailed error information
- Verify LlamaStack connectivity
- Ensure all dependencies are properly installed

### Performance Metrics
- Response times tracked via correlation IDs
- Resource usage monitored via Kubernetes metrics
- Auto-scaling based on CPU and memory utilization
- Health checks ensure service availability

### Updates and Maintenance
- Container images automatically built on code changes
- Rolling updates supported via Kubernetes deployment
- Configuration changes via ConfigMap updates
- Zero-downtime deployments with readiness probes