name 'nginx-webapp'
maintainer 'DevOps Team'
maintainer_email 'devops@company.com'
license 'Apache-2.0'
description 'Installs and configures Nginx web server with custom webapp'
version '2.1.0'
chef_version '>= 15.3'

supports 'ubuntu', '>= 18.04'
supports 'centos', '>= 7.0'

depends 'compat_resource', '>= 12.16.3'
depends 'systemd', '>= 1.2.4'
depends 'firewall', '~> 2.5'

issues_url 'https://github.com/company/nginx-webapp/issues'
source_url 'https://github.com/company/nginx-webapp'
