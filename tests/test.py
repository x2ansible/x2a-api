#!/usr/bin/env python3
"""
Standalone test script to test context agent fetching from chef analysis sessions.
Run this file directly: python tests/test.py
"""

import asyncio
import sys
import os
import uuid
import logging
from pathlib import Path

# Add the project root to the path so we can import modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.config import ConfigLoader
from agents.chef_analysis.agent import create_chef_analysis_agent
from agents.context_agent.context_agent import create_context_agent
from llama_stack_client.types import UserMessage

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TestScript")

class ContextAgentTester:
    def __init__(self):
        self.config_loader = ConfigLoader("config.yaml")
        self.chef_agent = None
        self.context_agent = None
        
    async def setup_agents(self):
        """Initialize both agents"""
        try:
            logger.info("Setting up agents...")
            self.chef_agent = create_chef_analysis_agent(self.config_loader)
            self.context_agent = create_context_agent(self.config_loader)
            logger.info("✓ Both agents initialized successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to setup agents: {e}")
            return False
    
    async def create_chef_session_with_cookbook(self):
        """Create a chef analysis session with sample cookbook data"""
        logger.info("Creating chef analysis session with sample cookbook...")
        
        # Sample cookbook data
        test_cookbook = {
            "name": "nginx-cookbook",
            "files": {
                "metadata.rb": """
name 'nginx'
maintainer 'DevOps Team'
maintainer_email 'devops@example.com'
license 'Apache-2.0'
description 'Installs/Configures nginx web server'
version '1.0.0'
chef_version '>= 14.0'

depends 'apt'
supports 'ubuntu'
supports 'debian'
""",
                "recipes/default.rb": """
#
# Cookbook:: nginx
# Recipe:: default
#

apt_update 'update_sources' do
  action :update
end

package 'nginx' do
  action :install
end

service 'nginx' do
  action [:enable, :start]
  supports :restart => true, :reload => true
end

template '/etc/nginx/nginx.conf' do
  source 'nginx.conf.erb'
  owner 'root'
  group 'root'
  mode '0644'
  notifies :restart, 'service[nginx]', :delayed
end

cookbook_file '/var/www/html/index.html' do
  source 'index.html'
  owner 'www-data'
  group 'www-data'
  mode '0644'
end
""",
                "attributes/default.rb": """
default['nginx']['worker_processes'] = 'auto'
default['nginx']['worker_connections'] = 1024
default['nginx']['keepalive_timeout'] = 65
default['nginx']['server_names_hash_bucket_size'] = 64
""",
                "templates/nginx.conf.erb": """
user www-data;
worker_processes <%= node['nginx']['worker_processes'] %>;
pid /run/nginx.pid;

events {
    worker_connections <%= node['nginx']['worker_connections'] %>;
}

http {
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout <%= node['nginx']['keepalive_timeout'] %>;
    
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    
    include /etc/nginx/conf.d/*.conf;
    include /etc/nginx/sites-enabled/*;
}
"""
            }
        }
        
        try:
            # Format cookbook content like the chef agent does
            cookbook_content = f"Cookbook: {test_cookbook['name']}\n"
            for filename, content in test_cookbook['files'].items():
                cookbook_content += f"\n=== {filename} ===\n{content.strip()}\n"
            
            # Get the chef agent ID (UUID)
            chef_agent_id = self.chef_agent.agent.agent_id
            logger.info(f"Chef agent ID: {chef_agent_id}")
            
            # Create chef session
            session_id = self.chef_agent.agent.create_session(f"test_{uuid.uuid4()}")
            logger.info(f"Created chef session: {session_id}")
            
            # Create turn with cookbook data
            turn = self.chef_agent.agent.create_turn(
                session_id=session_id,
                messages=[UserMessage(role="user", content=cookbook_content)],
                stream=False
            )
            
            logger.info(f"✓ Chef session created with cookbook data ({len(cookbook_content)} chars)")
            
            return {
                "agent_id": chef_agent_id,  # Return the actual UUID
                "session_id": session_id,
                "turn_id": getattr(turn, 'id', 'unknown'),
                "cookbook_name": test_cookbook['name'],
                "content_length": len(cookbook_content),
                "files_count": len(test_cookbook['files'])
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to create chef session: {e}")
            raise
    
    async def test_context_agent_fetch(self, chef_session_info):
        """Test context agent fetching from chef session"""
        logger.info("Testing context agent fetch from chef session...")
        
        try:
            result = await self.context_agent.query_context(
                code=None,  # Don't provide code directly
                previous_agent_id=chef_session_info["agent_id"],  # Use the actual UUID
                previous_session_id=chef_session_info["session_id"],
                top_k=5,
                correlation_id=f"test_{uuid.uuid4()}"
            )
            
            logger.info(f"✓ Context agent fetch completed")
            logger.info(f"  - Retrieved {result.get('input_code_length', 0)} characters")
            logger.info(f"  - Found {len(result.get('context', []))} context chunks")
            logger.info(f"  - Processing time: {result.get('elapsed_time', 0):.3f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Context agent fetch failed: {e}")
            raise
    
    async def run_full_test(self):
        """Run the complete test flow"""
        print("🚀 Starting Context Agent Test Flow")
        print("=" * 50)
        
        try:
            # Step 1: Setup agents
            print("\n📋 Step 1: Setting up agents...")
            if not await self.setup_agents():
                return False
            
            # Step 2: Create chef session
            print("\n👨‍🍳 Step 2: Creating chef analysis session...")
            chef_session = await self.create_chef_session_with_cookbook()
            
            print(f"   Agent ID: {chef_session['agent_id']}")
            print(f"   Session ID: {chef_session['session_id']}")
            print(f"   Cookbook: {chef_session['cookbook_name']}")
            print(f"   Files: {chef_session['files_count']}")
            print(f"   Content size: {chef_session['content_length']} chars")
            
            # Step 3: Test context fetch
            print("\n🔍 Step 3: Testing context agent fetch...")
            context_result = await self.test_context_agent_fetch(chef_session)
            
            # Step 4: Display results
            print("\n📊 Results Summary:")
            print("-" * 30)
            print(f"✓ Chef session created: {chef_session['session_id']}")
            print(f"✓ Context fetch successful: {context_result.get('input_code_length', 0) > 0}")
            print(f"✓ Context chunks found: {len(context_result.get('context', []))}")
            print(f"✓ Processing time: {context_result.get('elapsed_time', 0):.3f}s")
            
            # Show sample context
            context_chunks = context_result.get('context', [])
            if context_chunks:
                print(f"\n📝 Sample Context (first 2 chunks):")
                for i, chunk in enumerate(context_chunks[:2]):
                    preview = chunk.get('text', '')[:200]
                    print(f"   {i+1}. {preview}...")
                
                if len(context_chunks) > 2:
                    print(f"   ... and {len(context_chunks) - 2} more chunks")
            
            # Manual testing info
            print(f"\n🔧 For Manual API Testing:")
            print(f"POST /context/query")
            print(f"{{")
            print(f'  "previous_agent_id": "{chef_session["agent_id"]}",')
            print(f'  "previous_session_id": "{chef_session["session_id"]}",')
            print(f'  "top_k": 5')
            print(f"}}")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            logger.error(f"Full test failed: {e}", exc_info=True)
            return False

async def main():
    """Main test function"""
    tester = ContextAgentTester()
    success = await tester.run_full_test()
    
    if success:
        print("\n🎉 All tests passed! Your context agent can successfully fetch from chef sessions.")
    else:
        print("\n💥 Tests failed. Check the logs above for details.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())