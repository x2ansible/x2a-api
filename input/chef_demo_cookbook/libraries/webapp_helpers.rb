#
# Cookbook:: nginx-webapp
# Library:: webapp_helpers
#

module NginxWebapp
  module Helpers
    
    # Helper method to determine if SSL should be enabled
    def ssl_enabled?
      node['nginx']['webapp']['ssl']['enabled'] == true
    end
    
    # Helper to get the correct nginx service name
    def nginx_service_name
      case node['platform_family']
      when 'debian'
        'nginx'
      when 'rhel', 'fedora'
        'nginx'
      else
        'nginx'
      end
    end
    
    # Helper to validate server configuration
    def validate_server_config
      errors = []
      
      # Check required attributes
      if node['nginx']['webapp']['server_name'].nil? || node['nginx']['webapp']['server_name'].empty?
        errors << 'Server name cannot be empty'
      end
      
      if node['nginx']['webapp']['document_root'].nil? || node['nginx']['webapp']['document_root'].empty?
        errors << 'Document root cannot be empty'
      end
      
      # SSL validation
      if ssl_enabled?
        unless ::File.exist?(node['nginx']['webapp']['ssl']['cert_file'])
          errors << 'SSL certificate file not found'
        end
        
        unless ::File.exist?(node['nginx']['webapp']['ssl']['key_file'])
          errors << 'SSL key file not found'
        end
      end
      
      errors
    end
    
    # Check if firewall should be configured
    def configure_firewall?
      node['nginx']['firewall']['enabled'] == true && 
      node.run_list.include?('recipe[firewall]')
    end
    
  end
end

# Make helpers available to recipes
Chef::Recipe.include(NginxWebapp::Helpers)
Chef::Resource.include(NginxWebapp::Helpers)
