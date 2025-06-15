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
