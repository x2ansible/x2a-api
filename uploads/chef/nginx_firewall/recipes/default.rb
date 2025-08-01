#
# Cookbook:: nginx_firewall
# Recipe:: default
#
package 'nginx'

service 'nginx' do
  action [:enable, :start]
end

include_recipe 'nginx_firewall::firewall'

template '/etc/nginx/nginx.conf' do
  source 'nginx.conf.erb'
  notifies :reload, 'service[nginx]', :immediately
end
