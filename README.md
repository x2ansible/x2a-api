# X2A API 

## Overview

The X2A API is a FastAPI application that provides multiple specialized agents that handle Chef cookbook analysis, code generation, validation, and context retrieval using LlamaStack .

## Architecture



### Core Components

- **FastAPI Application**: Multi-agent REST API platform
- **LlamaStack Integration**: AI analysis engine using `meta-llama/Llama-3.1-8B-Instruct`
- **MCP Tools**: Model Context Protocol integration for ansible-lint validation
- **Gunicorn/Uvicorn**: ASGI server for production deployment

### Container Image

The service is packaged using UBI 9 Python 3.11 base image:

```
ghcr.io/x2ansible/x2a-api:latest
```

## Available Agents

### 1. Chef Analysis Agent (`/api/chef/*`)
Analyzes Chef cookbooks for migration planning.

**Features:**
- Version requirement analysis (Chef/Ruby versions)
- Dependency mapping and wrapper detection
- Migration effort estimation
- Consolidation recommendations

### 2. Context Agent (`/api/context/*`)
Retrieves infrastructure context using RAG (Retrieval-Augmented Generation).

**Features:**
- Knowledge search with vector database (ChromaDB)
- Best practices retrieval
- Pattern matching for infrastructure components

### 3. Generate Agent (`/api/generate/*`)
Generates Ansible playbooks from input code.

**Features:**
- Code conversion (Chef/Puppet → Ansible)
- Context-aware playbook generation
- YAML format output without markdown wrappers

### 4. Validate Agent (`/api/validate/*`)
Validates Ansible playbooks using MCP ansible-lint integration.

**Features:**
- Multiple validation profiles (basic, moderate, safety, shared, production)
- Real-time streaming validation
- Timeout protection (prevents worker crashes)
- Size limits (50KB max for standard validation)
- Exit code and issue detection

## Key Endpoints

### Chef Analysis
```bash
# Analyze cookbook files
POST /api/chef/analyze
{
  "cookbook_name": "apache-cookbook",
  "files": {
    "metadata.rb": "name 'apache'\nversion '1.0.0'",
    "recipes/default.rb": "package 'httpd'"
  }
}

# Streaming analysis
POST /api/chef/analyze/stream
```

### Context Search
```bash
# Search knowledge base
POST /api/context/query
{
  "code": "nginx configuration",
  "top_k": 5
}

# Streaming search
POST /api/context/query/stream
```

### Code Generation
```bash
# Generate Ansible playbook
POST /api/generate/playbook
{
  "input_code": "package 'httpd' do\n  action :install\nend",
  "context": "Convert Chef resource to Ansible"
}

# Streaming generation
POST /api/generate/playbook/stream
```

### Playbook Validation
```bash
# Validate playbook with profile
POST /api/validate/playbook
{
  "playbook_content": "---\n- name: Test\n  hosts: all\n  tasks: []",
  "profile": "basic"
}

# Streaming validation
POST /api/validate/playbook/stream

# Available profiles
GET /api/validate/profiles
```

## Validation Features

### Profiles
- **basic**: Syntax and structure validation
- **moderate**: Standard best practices checking
- **safety**: Security-focused validation rules
- **shared**: Rules for shared/reusable playbooks
- **production**: Strict production-ready validation

### Timeout Protection
- **Playbook validation**: 2 minutes
- **Syntax check**: 1 minute
- **Production validation**: 3 minutes
- **Multiple files**: 5 minutes
- **Streaming**: 2.5 minutes

### Size Limits
- **Standard validation**: 50KB
- **Syntax check**: 25KB
- **Production validation**: 30KB
- **Multiple files total**: 100KB

## Configuration

### Environment Variables
```bash
CONFIG_FILE=config.yaml
UPLOAD_DIR=/tmp/uploads
LLAMASTACK_URL=http://lss-chai.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com
```

### Agent Configuration (config.yaml)
```yaml
llamastack:
  base_url: "http://lss-chai.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com"
  default_model: "meta-llama/Llama-3.1-8B-Instruct"

agents:
  - name: "chef_analysis_chaining"
    model: "meta-llama/Llama-3.1-8B-Instruct"
    instructions: "You are an expert Chef cookbook analyst..."
    
  - name: "context"
    model: "meta-llama/Llama-3.1-8B-Instruct"
    tools:
      - name: "builtin::rag"
        args:
          vector_db_ids: ["iac"]
          
  - name: "generate"
    model: "meta-llama/Llama-3.1-8B-Instruct"
    tools:
      - name: "builtin::rag"
        args:
          vector_db_ids: ["iac"]
          
  - name: "validate"
    model: "meta-llama/Llama-3.1-8B-Instruct"
    toolgroups: ["mcp::ansible_lint"]
    tool_config:
      tool_choice: "auto"
    max_infer_iters: 5
```

## Deployment

### Podman
```containerfile
FROM registry.access.redhat.com/ubi9/python-311:latest

WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /tmp/uploads
ENV UPLOAD_DIR=/tmp/uploads

EXPOSE 8000
CMD ["gunicorn", "--timeout", "360", "-w", "1", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "main:app"]
```

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Start development server
gunicorn --timeout 360 --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 main:app

# Or with uvicorn for development
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Health Monitoring

### Health Endpoints
```bash
# Overall application status
GET /

# Individual agent status
GET /api/chef/health
GET /api/context/health  
GET /api/generate/health
GET /api/validate/health

# Agent information
GET /api/agents/status
```

### Debug Endpoints
```bash
# Check MCP tool availability
GET /api/validate/debug/tools

# Test tool functionality
POST /api/validate/debug/test-tool
```

## Usage Examples

### Chef Analysis
```bash
curl -X POST "http://localhost:8000/api/chef/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "cookbook_name": "apache",
    "files": {
      "metadata.rb": "name \"apache\"\nversion \"1.0.0\"\nchef_version \">= 15.0\"",
      "recipes/default.rb": "package \"httpd\" do\n  action :install\nend"
    }
  }'
```

### Validation with Different Profiles
```bash
# Basic validation
curl -X POST "http://localhost:8000/api/validate/playbook" \
  -H "Content-Type: application/json" \
  -d '{
    "playbook_content": "---\n- name: Test\n  hosts: all\n  tasks:\n    - debug: msg=\"Hello\"\n",
    "profile": "basic"
  }'

# Production validation (stricter)
curl -X POST "http://localhost:8000/api/validate/playbook" \
  -H "Content-Type: application/json" \
  -d '{
    "playbook_content": "---\n- name: Production playbook\n  hosts: all\n  become: true\n  tasks:\n    - name: Install nginx\n      package:\n        name: nginx\n        state: present\n",
    "profile": "production"
  }'
```

### Streaming Validation
```bash
curl -N -X POST "http://localhost:8000/api/validate/playbook/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "playbook_content": "---\n- name: Test\n  hosts: all\n  tasks: []",
    "profile": "safety"
  }'
```

## API Documentation

Interactive documentation available at:
```
http://localhost:8000/docs
```

## Technical Details

### Registry Pattern
- Prevents duplicate agent creation
- Reuses existing agents across application restarts
- Session management per validation request

### MCP Integration
- Uses Model Context Protocol for ansible-lint
- Structured JSON responses from linting tools
- Profile-based validation rules

### Timeout Handling
- AsyncIO timeout wrappers prevent worker crashes
- Graceful error responses for timeouts
- Different timeout limits per endpoint type

### Streaming Support
- Server-Sent Events (SSE) for real-time updates
- Progress tracking for long-running operations
- Error handling within streams

## Error Handling

### Common HTTP Status Codes
- **200**: Success
- **400**: Bad Request (invalid profile, malformed input)
- **408**: Request Timeout (validation took too long)
- **413**: Payload Too Large (exceeds size limits)
- **500**: Internal Server Error
- **503**: Service Unavailable (agent not ready)

### Timeout Responses
```json
{
  "success": false,
  "error": "Validation timeout: Validation timed out after 120 seconds",
  "timeout": true,
  "elapsed_time": 120.5
}
```

## Troubleshooting

### Worker Timeout Issues
- Increase gunicorn timeout: `--timeout 360`
- Use single worker: `-w 1`
- Check playbook size limits

### MCP Tool Issues
- Verify ansible-lint toolgroup availability
- Check LlamaStack connectivity
- Review agent configuration

### Performance Issues
- Monitor resource usage
- Consider size limits
- Use appropriate validation profiles

## Contributing

### Development Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Set environment variables
3. Start development server
4. Test endpoints using Swagger UI at `/docs`

### Testing Validation
Use the test endpoint for quick validation testing:
```bash
POST /api/validate/test
```