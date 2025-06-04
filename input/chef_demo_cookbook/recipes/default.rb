#
# Cookbook:: nginx-webapp
# Recipe:: default
#
# Copyright:: 2023, Company Inc., All Rights Reserved.

# Enable unified mode (Chef 15+ feature)
unified_mode true

# Install Nginx package
package node['nginx']['package_name'] do
  action :install
  version node['nginx']['version'] if node['nginx']['version']
end

# Create nginx configuration directory
directory '/etc/nginx/conf.d' do
  owner 'root'
  group 'root'
  mode '0755'
  recursive true
end

# Create main nginx configuration
template '/etc/nginx/nginx.conf' do
  source 'nginx.conf.erb'
  owner 'root'
  group 'root'
  mode '0644'
  variables(
    worker_processes: node['nginx']['worker_processes'],
    worker_connections: node['nginx']['worker_connections'],
    keepalive_timeout: node['nginx']['keepalive_timeout']
  )
  notifies :reload, 'service[nginx]', :delayed
end

# Create webapp configuration
template '/etc/nginx/conf.d/webapp.conf' do
  source 'webapp.conf.erb'
  owner 'root'
  group 'root'
  mode '0644'
  variables(
    server_name: node['nginx']['webapp']['server_name'],
    document_root: node['nginx']['webapp']['document_root'],
    ssl_enabled: node['nginx']['webapp']['ssl']['enabled']
  )
  notifies :reload, 'service[nginx]', :delayed
end

# Create document root directory
directory node['nginx']['webapp']['document_root'] do
  owner node['nginx']['user']
  group node['nginx']['group']
  mode '0755'
  recursive true
end

# Deploy sample index page
cookbook_file "#{node['nginx']['webapp']['document_root']}/index.html" do
  source 'index.html'
  owner node['nginx']['user']
  group node['nginx']['group']
  mode '0644'
end

# Enable and start Nginx service
service 'nginx' do
  supports restart: true, reload: true, status: true
  action [:enable, :start]
end

# Configure firewall if enabled
if node['nginx']['firewall']['enabled']
  firewall_rule 'http' do
    port 80
    protocol :tcp
    action :allow
  end

  if node['nginx']['webapp']['ssl']['enabled']
    firewall_rule 'https' do
      port 443
      protocol :tcp
      action :allow
    end
  end
end

# Include SSL configuration if enabled
include_recipe 'nginx-webapp::ssl' if node['nginx']['webapp']['ssl']['enabled']

# Log configuration completion
log 'nginx-webapp-configured' do
  message "Nginx webapp configured successfully for #{node['nginx']['webapp']['server_name']}"
  level :info
end
