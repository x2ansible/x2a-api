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
