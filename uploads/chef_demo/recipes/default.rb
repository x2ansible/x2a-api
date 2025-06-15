include_recipe "complex_webapp::web"
include_recipe "complex_webapp::database"
include_recipe "complex_webapp::monitoring"

directory "/opt/webapp" do
  owner "www-data"
  group "www-data"
  mode "0755"
  recursive true
end

package "prometheus-node-exporter"

service "prometheus-node-exporter" do
  action [:enable, :start]
end

template "/etc/prometheus/node_exporter.yml" do
  source "node_exporter.yml.erb"
  variables(
    scrape_interval: "15s"
  )
end

package "nginx"

service "nginx" do
  action [:enable, :start]
  supports reload: true
end

template "/etc/nginx/sites-available/webapp.conf" do
  source "webapp.conf.erb"
  variables(
    server_name: "example.com",
    ssl_cert: "/etc/ssl/certs/webapp.crt",
    ssl_key: "/etc/ssl/private/webapp.key"
  )
  notifies :reload, "service[nginx]"
end

cookbook_file "/opt/webapp/index.html" do
  source "index.html"
  owner "www-data"
  group "www-data"
  mode "0644"
end
