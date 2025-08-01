firewalld_service 'http' do
  action :add
  zone   'public'
  notifies :reload, 'firewalld_reload[reload-firewalld]', :immediately
end

firewalld_reload 'reload-firewalld' do
  action :nothing
end
