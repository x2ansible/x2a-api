#
# Cookbook:: nginx-webapp
# Attributes:: default
#

# Platform-specific package names
default['nginx']['package_name'] = case node['platform_family']
                                   when 'debian'
                                     'nginx'
                                   when 'rhel', 'fedora'
                                     'nginx'
                                   when 'suse'
                                     'nginx'
                                   else
                                     'nginx'
                                   end

# Platform-specific user/group
default['nginx']['user'] = case node['platform_family']
                           when 'debian'
                             'www-data'
                           when 'rhel', 'fedora', 'suse'
                             'nginx'
                           else
                             'nginx'
                           end

default['nginx']['group'] = case node['platform_family']
                            when 'debian'
                              'www-data'
                            when 'rhel', 'fedora', 'suse'
                              'nginx'
                            else
                              'nginx'
                            end

# Nginx performance settings
default['nginx']['worker_processes'] = 'auto'
default['nginx']['worker_connections'] = 1024
default['nginx']['keepalive_timeout'] = 65
default['nginx']['client_max_body_size'] = '64M'

# Webapp configuration
default['nginx']['webapp']['server_name'] = node['fqdn'] || 'localhost'
default['nginx']['webapp']['document_root'] = '/var/www/html'
default['nginx']['webapp']['index_files'] = ['index.html', 'index.htm']

# SSL configuration
default['nginx']['webapp']['ssl']['enabled'] = false
default['nginx']['webapp']['ssl']['cert_file'] = '/etc/nginx/ssl/nginx.crt'
default['nginx']['webapp']['ssl']['key_file'] = '/etc/nginx/ssl/nginx.key'
default['nginx']['webapp']['ssl']['protocols'] = 'TLSv1.2 TLSv1.3'
default['nginx']['webapp']['ssl']['ciphers'] = 'ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384'

# Logging configuration
default['nginx']['access_log'] = '/var/log/nginx/access.log'
default['nginx']['error_log'] = '/var/log/nginx/error.log'
default['nginx']['log_level'] = 'warn'

# Firewall settings
default['nginx']['firewall']['enabled'] = true

# Backup and monitoring
default['nginx']['backup']['enabled'] = false
default['nginx']['monitoring']['enabled'] = true
default['nginx']['monitoring']['status_page'] = '/nginx_status'
