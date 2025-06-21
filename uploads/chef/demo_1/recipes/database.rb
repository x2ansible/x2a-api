package "postgresql"

package "postgresql-contrib"

service "postgresql" do
  action [:enable, :start]
end

execute "create_db_user" do
  command "psql -c \"CREATE ROLE webuser WITH LOGIN PASSWORD 'securepass';\""
  user "postgres"
  not_if "psql -c '\\du' | grep webuser", user: "postgres"
end

execute "create_database" do
  command "createdb -O webuser webapp_db"
  user "postgres"
  not_if "psql -lqt | cut -d \\| -f 1 | grep -w webapp_db", user: "postgres"
end
