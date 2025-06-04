#
# Cookbook:: nginx-webapp
# Recipe:: ssl
#
# Copyright:: 2023, Company Inc., All Rights Reserved.

unified_mode true

# Create SSL directory
directory '/etc/nginx/ssl' do
  owner 'root'
  group 'root'
  mode '0700'
  recursive true
end

# Generate self-signed certificate if none provided
execute 'generate-ssl-cert' do
  command <<-EOC
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/nginx.key \
    -out /etc/nginx/ssl/nginx.crt \
    -subj "/C=US/ST=State/L=City/O=Company/CN=#{node['nginx']['webapp']['server_name']}"
  EOC
  creates '/etc/nginx/ssl/nginx.crt'
  notifies :reload, 'service[nginx]', :delayed
end

# Set proper permissions on SSL files
file '/etc/nginx/ssl/nginx.key' do
  owner 'root'
  group 'root'
  mode '0600'
end

file '/etc/nginx/ssl/nginx.crt' do
  owner 'root'
  group 'root'
  mode '0644'
end
