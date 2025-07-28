# Infrastructure as Code Conversion Patterns Database

## Chef to Ansible Conversion Patterns

### Package Management Conversion
**Chef Recipe Pattern:**
```ruby
# Chef cookbook recipe
package 'apache2' do
  action :install
  version '2.4.41-4ubuntu3.8'
end

service 'apache2' do
  action [:enable, :start]
  supports :restart => true, :reload => true
end
```

**Ansible Equivalent:**
```yaml
# Ansible playbook
- name: Install Apache web server
  package:
    name: apache2
    version: '2.4.41-4ubuntu3.8'
    state: present

- name: Enable and start Apache service
  service:
    name: apache2
    state: started
    enabled: yes
```

**Conversion Notes:** Chef's package resource maps directly to Ansible's package module. Chef's service actions :enable and :start become Ansible's enabled: yes and state: started.

### File Template Conversion
**Chef Template Pattern:**
```ruby
# Chef template resource
template '/etc/apache2/apache2.conf' do
  source 'apache2.conf.erb'
  owner 'root'
  group 'root'
  mode '0644'
  variables({
    server_name: node['apache']['server_name'],
    document_root: node['apache']['document_root']
  })
  notifies :restart, 'service[apache2]', :immediately
end
```

**Ansible Equivalent:**
```yaml
# Ansible template task
- name: Configure Apache main configuration
  template:
    src: apache2.conf.j2
    dest: /etc/apache2/apache2.conf
    owner: root
    group: root
    mode: '0644'
  vars:
    server_name: "{{ apache_server_name }}"
    document_root: "{{ apache_document_root }}"
  notify: restart apache2
```

**Conversion Notes:** Chef's template source becomes Ansible's src. Chef's variables parameter becomes Ansible's vars section. Chef's notifies become Ansible's notify.

### Directory Management Conversion
**Chef Directory Pattern:**
```ruby
# Chef directory resource
directory '/var/www/html/app' do
  owner 'www-data'
  group 'www-data'
  mode '0755'
  recursive true
  action :create
end

file '/var/www/html/app/index.html' do
  content '<h1>Welcome to our application</h1>'
  owner 'www-data'
  group 'www-data'
  mode '0644'
end
```

**Ansible Equivalent:**
```yaml
# Ansible directory and file tasks
- name: Create application directory
  file:
    path: /var/www/html/app
    state: directory
    owner: www-data
    group: www-data
    mode: '0755'
    recurse: yes

- name: Create application index file
  copy:
    content: '<h1>Welcome to our application</h1>'
    dest: /var/www/html/app/index.html
    owner: www-data
    group: www-data
    mode: '0644'
```

**Conversion Notes:** Chef's directory resource becomes Ansible's file module with state: directory. Chef's recursive true becomes Ansible's recurse: yes.

## Puppet to Ansible Conversion Patterns (Reference)

### Package and Service Management
**Puppet Manifest Pattern:**
```puppet
# Puppet manifest
class nginx {
  package { 'nginx':
    ensure => 'installed',
  }
  
  service { 'nginx':
    ensure  => 'running',
    enable  => true,
    require => Package['nginx'],
  }
  
  file { '/etc/nginx/nginx.conf':
    ensure  => 'present',
    source  => 'puppet:///modules/nginx/nginx.conf',
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    require => Package['nginx'],
    notify  => Service['nginx'],
  }
}
```

**Ansible Equivalent:**
```yaml
# Ansible playbook
- name: Install nginx package
  package:
    name: nginx
    state: present

- name: Configure nginx
  copy:
    src: nginx.conf
    dest: /etc/nginx/nginx.conf
    owner: root
    group: root
    mode: '0644'
  notify: restart nginx

- name: Start and enable nginx service
  service:
    name: nginx
    state: started
    enabled: yes
```

**Conversion Notes:** Puppet's ensure => 'installed' becomes state: present. Puppet's require becomes implicit ordering in Ansible. Puppet's notify becomes Ansible's notify.

### User Management Conversion
**Puppet User Pattern:**
```puppet
# Puppet user resource
user { 'webuser':
  ensure     => 'present',
  uid        => '1001',
  gid        => '1001',
  home       => '/home/webuser',
  shell      => '/bin/bash',
  managehome => true,
}

group { 'webgroup':
  ensure => 'present',
  gid    => '1001',
}
```

**Ansible Equivalent:**
```yaml
# Ansible user management
- name: Create webgroup
  group:
    name: webgroup
    gid: 1001
    state: present

- name: Create webuser
  user:
    name: webuser
    uid: 1001
    group: webgroup
    home: /home/webuser
    shell: /bin/bash
    create_home: yes
    state: present
```

**Conversion Notes:** Puppet's managehome => true becomes Ansible's create_home: yes. Puppet's ensure => 'present' becomes state: present.

### Conditional Logic Conversion
**Puppet Conditional Pattern:**
```puppet
# Puppet conditional
if $::operatingsystem == 'Ubuntu' {
  $apache_package = 'apache2'
  $apache_service = 'apache2'
} elsif $::operatingsystem == 'CentOS' {
  $apache_package = 'httpd'
  $apache_service = 'httpd'
}

package { $apache_package:
  ensure => 'installed',
}
```

**Ansible Equivalent:**
```yaml
# Ansible conditional with variables
- name: Set Apache package name (Ubuntu)
  set_fact:
    apache_package: apache2
    apache_service: apache2
  when: ansible_distribution == 'Ubuntu'

- name: Set Apache package name (CentOS)
  set_fact:
    apache_package: httpd
    apache_service: httpd
  when: ansible_distribution == 'CentOS'

- name: Install Apache package
  package:
    name: "{{ apache_package }}"
    state: present
```

**Conversion Notes:** Puppet's if/elsif becomes Ansible's when conditions. Puppet facts like $::operatingsystem become Ansible facts like ansible_distribution.

## Shell Script to Ansible Conversion Patterns

### System Update Script Conversion
**Shell Script Pattern:**
```bash
#!/bin/bash
# System update script
echo "Starting system update..."

# Update package lists
apt-get update -y

# Upgrade all packages
apt-get upgrade -y

# Install required packages
apt-get install -y curl wget git vim htop

# Clean up
apt-get autoremove -y
apt-get autoclean

echo "System update completed successfully!"
```

**Ansible Equivalent:**
```yaml
# Ansible system update playbook
- name: Starting system update
  debug:
    msg: "Starting system update..."

- name: Update package cache
  apt:
    update_cache: yes
    cache_valid_time: 3600

- name: Upgrade all packages
  apt:
    upgrade: dist

- name: Install required packages
  apt:
    name:
      - curl
      - wget
      - git
      - vim
      - htop
    state: present

- name: Remove unnecessary packages
  apt:
    autoremove: yes
    autoclean: yes

- name: System update completed
  debug:
    msg: "System update completed successfully!"
```

**Conversion Notes:** Shell commands become Ansible modules. apt-get becomes apt module. Multiple package installations become a list under name.

### Service Configuration Script
**Shell Script Pattern:**
```bash
#!/bin/bash
# MySQL setup script
MYSQL_ROOT_PASSWORD="SecurePass123"

# Install MySQL
apt-get install -y mysql-server mysql-client

# Start MySQL service
systemctl enable mysql
systemctl start mysql

# Secure MySQL installation
mysql -uroot <<-EOF
UPDATE mysql.user SET authentication_string=PASSWORD('${MYSQL_ROOT_PASSWORD}') WHERE User='root';
DELETE FROM mysql.user WHERE User='root' AND Host NOT IN ('localhost', '127.0.0.1', '::1');
DELETE FROM mysql.user WHERE User='';
DELETE FROM mysql.db WHERE Db='test' OR Db='test_%';
FLUSH PRIVILEGES;
EOF

echo "MySQL installation and configuration completed!"
```

**Ansible Equivalent:**
```yaml
# Ansible MySQL setup
- name: Install MySQL packages
  apt:
    name:
      - mysql-server
      - mysql-client
      - python3-pymysql
    state: present

- name: Start and enable MySQL service
  service:
    name: mysql
    state: started
    enabled: yes

- name: Set MySQL root password
  mysql_user:
    name: root
    password: "{{ mysql_root_password }}"
    login_unix_socket: /var/run/mysqld/mysqld.sock
    state: present

- name: Remove anonymous MySQL users
  mysql_user:
    name: ''
    host_all: yes
    state: absent
    login_user: root
    login_password: "{{ mysql_root_password }}"

- name: Remove test database
  mysql_db:
    name: test
    state: absent
    login_user: root
    login_password: "{{ mysql_root_password }}"

- name: MySQL setup completed
  debug:
    msg: "MySQL installation and configuration completed!"
```

**Conversion Notes:** Shell script commands become specific Ansible modules. mysql_user and mysql_db modules replace raw MySQL commands. Variables use Ansible syntax {{ variable_name }}.

### Log Rotation Script Conversion
**Shell Script Pattern:**
```bash
#!/bin/bash
# Log rotation script
LOG_DIR="/var/log/myapp"
RETENTION_DAYS=30

# Create log directory if it doesn't exist
mkdir -p $LOG_DIR

# Find and compress old log files
find $LOG_DIR -name "*.log" -type f -mtime +1 -exec gzip {} \;

# Remove log files older than retention period
find $LOG_DIR -name "*.log.gz" -type f -mtime +$RETENTION_DAYS -delete

# Create logrotate configuration
cat > /etc/logrotate.d/myapp << EOF
$LOG_DIR/*.log {
    daily
    missingok
    rotate 30
    compress
    notifempty
    create 644 myapp myapp
}
EOF

systemctl restart rsyslog
```

**Ansible Equivalent:**
```yaml
# Ansible log rotation setup
- name: Create log directory
  file:
    path: /var/log/myapp
    state: directory
    owner: myapp
    group: myapp
    mode: '0755'

- name: Compress old log files
  shell: find /var/log/myapp -name "*.log" -type f -mtime +1 -exec gzip {} \;
  register: compress_result
  changed_when: compress_result.stdout != ""

- name: Remove old compressed logs
  shell: find /var/log/myapp -name "*.log.gz" -type f -mtime +{{ retention_days }} -delete
  vars:
    retention_days: 30

- name: Configure logrotate for myapp
  copy:
    dest: /etc/logrotate.d/myapp
    content: |
      /var/log/myapp/*.log {
          daily
          missingok
          rotate 30
          compress
          notifempty
          create 644 myapp myapp
      }
    owner: root
    group: root
    mode: '0644'
  notify: restart rsyslog

- name: Define restart rsyslog handler
  handlers:
    - name: restart rsyslog
      service:
        name: rsyslog
        state: restarted
```

**Conversion Notes:** File operations become file module tasks. Complex shell commands can remain as shell module with proper change detection. Heredoc content becomes Ansible copy module with content parameter.

## BladeLogic to Ansible Conversion Patterns

### BladeLogic NSH Script Conversion
**BladeLogic NSH Pattern:**
```bash
# BladeLogic NSH script
nexec -e "yum install -y httpd"
nexec -e "systemctl enable httpd"
nexec -e "systemctl start httpd"

# Deploy configuration file
ncp /tmp/httpd.conf ??TARGET.HOSTNAME??:/etc/httpd/conf/httpd.conf

# Set file permissions
nexec -e "chown root:root /etc/httpd/conf/httpd.conf"
nexec -e "chmod 644 /etc/httpd/conf/httpd.conf"

# Restart service
nexec -e "systemctl restart httpd"
```

**Ansible Equivalent:**
```yaml
# Ansible equivalent of BladeLogic NSH
- name: Install Apache HTTP Server
  yum:
    name: httpd
    state: present

- name: Deploy Apache configuration
  copy:
    src: httpd.conf
    dest: /etc/httpd/conf/httpd.conf
    owner: root
    group: root
    mode: '0644'
  notify: restart httpd

- name: Enable and start Apache service
  service:
    name: httpd
    state: started
    enabled: yes

handlers:
  - name: restart httpd
    service:
      name: httpd
      state: restarted
```

**Conversion Notes:** BladeLogic's nexec commands become native Ansible modules. ncp (network copy) becomes Ansible's copy module. BladeLogic variables like ??TARGET.HOSTNAME?? become Ansible inventory variables.

### BladeLogic Package Deployment
**BladeLogic Batch Job Pattern:**
```bash
# BladeLogic batch job for software deployment
# Deploy RPM package
blcli_execute BatchJob createJob "Deploy Application"
blcli_execute DeployJob addTarget "Deploy Application" "//Server Group/Web Servers"
blcli_execute DeployJob addPackage "Deploy Application" "myapp-1.2.3.rpm"

# Execute deployment
blcli_execute Job execute "Deploy Application"

# Verify deployment
nexec -e "rpm -qa | grep myapp"
nexec -e "systemctl status myapp"
```

**Ansible Equivalent:**
```yaml
# Ansible application deployment
- name: Deploy application RPM
  yum:
    name: /tmp/myapp-1.2.3.rpm
    state: present
    disable_gpg_check: yes
  register: rpm_install

- name: Start and enable application service
  service:
    name: myapp
    state: started
    enabled: yes
  when: rpm_install.changed

- name: Verify application installation
  command: rpm -qa myapp
  register: rpm_verify
  changed_when: false

- name: Check application service status
  command: systemctl is-active myapp
  register: service_status
  changed_when: false

- name: Display installation verification
  debug:
    msg: "Application installed: {{ rpm_verify.stdout }}, Service status: {{ service_status.stdout }}"
```

**Conversion Notes:** BladeLogic's batch jobs become Ansible playbooks. BladeLogic's server groups become Ansible inventory groups. BladeLogic's package deployment becomes yum/package module.

### BladeLogic Compliance Policy Conversion
**BladeLogic Compliance Template:**
```bash
# BladeLogic compliance check
# Check SSH configuration
nexec -e "grep '^PermitRootLogin' /etc/ssh/sshd_config"
# Expected: PermitRootLogin no

# Check firewall status
nexec -e "systemctl is-active firewalld"
# Expected: active

# Check user accounts
nexec -e "awk -F: '$3 >= 1000 && $3 < 65534 {print $1}' /etc/passwd"
```

**Ansible Equivalent:**
```yaml
# Ansible compliance checking
- name: Check SSH root login configuration
  lineinfile:
    path: /etc/ssh/sshd_config
    regexp: '^PermitRootLogin'
    line: 'PermitRootLogin no'
    state: present
  check_mode: yes
  register: ssh_compliance
  
- name: Ensure firewall is active
  service:
    name: firewalld
    state: started
    enabled: yes
  check_mode: yes
  register: firewall_compliance

- name: Get list of regular user accounts
  shell: "awk -F: '$3 >= 1000 && $3 < 65534 {print $1}' /etc/passwd"
  register: user_accounts
  changed_when: false

- name: Generate compliance report
  debug:
    msg: 
      - "SSH Configuration Compliant: {{ not ssh_compliance.changed }}"
      - "Firewall Service Compliant: {{ not firewall_compliance.changed }}"
      - "Regular User Accounts: {{ user_accounts.stdout_lines }}"
```

**Conversion Notes:** BladeLogic compliance checks become Ansible tasks with check_mode for verification. BladeLogic's expected values become Ansible's desired state declarations.

## Salt to Ansible Conversion Patterns

### Salt State File Conversion
**Salt State Pattern:**
```yaml
# Salt state file (nginx.sls)
nginx:
  pkg.installed:
    - name: nginx
  service.running:
    - name: nginx
    - enable: True
    - require:
      - pkg: nginx

/etc/nginx/nginx.conf:
  file.managed:
    - source: salt://nginx/files/nginx.conf
    - user: root
    - group: root
    - mode: 644
    - require:
      - pkg: nginx
    - watch_in:
      - service: nginx
```

**Ansible Equivalent:**
```yaml
# Ansible playbook equivalent
- name: Install nginx package
  package:
    name: nginx
    state: present

- name: Configure nginx
  copy:
    src: nginx.conf
    dest: /etc/nginx/nginx.conf
    owner: root
    group: root
    mode: '0644'
  notify: restart nginx

- name: Start and enable nginx service
  service:
    name: nginx
    state: started
    enabled: yes

handlers:
  - name: restart nginx
    service:
      name: nginx
      state: restarted
```

**Conversion Notes:** Salt's pkg.installed becomes package module. Salt's service.running becomes service module with state: started. Salt's watch_in becomes Ansible's notify/handlers pattern.

### Salt Pillar Data Conversion
**Salt Pillar Pattern:**
```yaml
# Salt pillar data
mysql:
  root_password: 'MySecurePassword123'
  databases:
    - name: 'webapp'
      encoding: 'utf8'
      collate: 'utf8_general_ci'
  users:
    - name: 'webuser'
      password: 'WebUserPass456'
      host: 'localhost'
      grants:
        - 'webapp.*:SELECT,INSERT,UPDATE,DELETE'
```

**Salt State Using Pillar:**
```yaml
# Salt state using pillar
mysql-server:
  pkg.installed

mysql:
  service.running:
    - require:
      - pkg: mysql-server

{% for db in salt['pillar.get']('mysql:databases', []) %}
{{ db.name }}:
  mysql_database.present:
    - name: {{ db.name }}
    - character_set: {{ db.encoding }}
    - collate: {{ db.collate }}
    - connection_user: root
    - connection_pass: {{ salt['pillar.get']('mysql:root_password') }}
{% endfor %}
```

**Ansible Equivalent:**
```yaml
# Ansible variables (group_vars or host_vars)
mysql:
  root_password: 'MySecurePassword123'
  databases:
    - name: 'webapp'
      encoding: 'utf8'
      collate: 'utf8_general_ci'
  users:
    - name: 'webuser'
      password: 'WebUserPass456'
      host: 'localhost'
      grants:
        - 'webapp.*:SELECT,INSERT,UPDATE,DELETE'

# Ansible playbook
- name: Install MySQL server
  package:
    name: mysql-server
    state: present

- name: Start MySQL service
  service:
    name: mysql
    state: started
    enabled: yes

- name: Create MySQL databases
  mysql_db:
    name: "{{ item.name }}"
    encoding: "{{ item.encoding }}"
    collation: "{{ item.collate }}"
    state: present
    login_user: root
    login_password: "{{ mysql.root_password }}"
  loop: "{{ mysql.databases }}"

- name: Create MySQL users
  mysql_user:
    name: "{{ item.name }}"
    password: "{{ item.password }}"
    host: "{{ item.host }}"
    priv: "{{ item.grants | join('/') }}"
    state: present
    login_user: root
    login_password: "{{ mysql.root_password }}"
  loop: "{{ mysql.users }}"
```

**Conversion Notes:** Salt Pillar data becomes Ansible variables. Salt's Jinja templating in states becomes Ansible's loop constructs. Salt's mysql_database.present becomes mysql_db module.

### Salt Grain-based Conditionals
**Salt Grain Pattern:**
```yaml
# Salt state with grains
{% if grains['os'] == 'Ubuntu' %}
apache2:
  pkg.installed
  service.running:
    - name: apache2
{% elif grains['os'] == 'CentOS' %}
httpd:
  pkg.installed
  service.running:
    - name: httpd
{% endif %}

# Salt custom grain
/etc/salt/grains:
  file.managed:
    - contents: |
        application_role: webserver
        environment: production
```

**Ansible Equivalent:**
```yaml
# Ansible facts-based conditionals
- name: Install Apache on Ubuntu
  package:
    name: apache2
    state: present
  when: ansible_distribution == 'Ubuntu'

- name: Start Apache service on Ubuntu
  service:
    name: apache2
    state: started
    enabled: yes
  when: ansible_distribution == 'Ubuntu'

- name: Install Apache on CentOS
  package:
    name: httpd
    state: present
  when: ansible_distribution == 'CentOS'

- name: Start Apache service on CentOS
  service:
    name: httpd
    state: started
    enabled: yes
  when: ansible_distribution == 'CentOS'

# Ansible custom facts
- name: Set custom facts
  set_fact:
    application_role: webserver
    environment: production

- name: Create custom facts file
  copy:
    content: |
      [general]
      application_role=webserver
      environment=production
    dest: /etc/ansible/facts.d/custom.fact
    mode: '0644'
```

**Conversion Notes:** Salt grains become Ansible facts. Salt's conditional templating becomes Ansible's when conditions. Salt's custom grains become Ansible's custom facts in /etc/ansible/facts.d/.

## Ansible Version Upgrade Patterns

### Ansible 2.9 to Ansible Core 2.12+ Migration
**Legacy Ansible 2.9 Pattern:**
```yaml
# Old Ansible 2.9 syntax
- name: Install packages
  yum:
    name: "{{ item }}"
    state: present
  with_items:
    - httpd
    - php
    - mysql-server
  
# Old import syntax
- include: database.yml

# Old become syntax
- name: Configure service
  template:
    src: config.j2
    dest: /etc/service/config
  become_user: root
  become: true
```

**Ansible Core 2.12+ Equivalent:**
```yaml
# Modern Ansible syntax
- name: Install packages
  yum:
    name:
      - httpd
      - php
      - mysql-server
    state: present

# New import syntax
- name: Include database tasks
  import_tasks: database.yml

# Streamlined privilege escalation
- name: Configure service
  template:
    src: config.j2
    dest: /etc/service/config
  become: yes
```

**Conversion Notes:** Replace with_items loops with direct list syntax. Use import_tasks instead of include. Simplify become syntax. Update deprecated modules.

### Ansible Collections Migration
**Pre-Collections Pattern:**
```yaml
# Old built-in modules
- name: Manage AWS EC2 instance
  ec2:
    key_name: mykey
    instance_type: t2.micro
    image: ami-12345678
    wait: yes
    group: webserver
    count: 1
    
- name: Configure MySQL
  mysql_user:
    name: webapp
    password: secretpass
    priv: '*.*:ALL'
    state: present
```

**Collections-Based Pattern:**
```yaml
# Modern collections usage
- name: Manage AWS EC2 instance
  amazon.aws.ec2_instance:
    key_name: mykey
    instance_type: t2.micro
    image_id: ami-12345678
    wait: yes
    security_group: webserver
    count: 1
    state: running

- name: Configure MySQL user
  community.mysql.mysql_user:
    name: webapp
    password: secretpass
    priv: '*.*:ALL'
    state: present
```

**Required Collections:**
```yaml
# requirements.yml
---
collections:
  - name: amazon.aws
    version: ">=5.0.0"
  - name: community.mysql
    version: ">=3.0.0"
  - name: ansible.posix
    version: ">=1.3.0"
```

**Conversion Notes:** Migrate to FQCN (Fully Qualified Collection Names). Update module parameters that have changed. Create requirements.yml for dependencies. Use ansible-galaxy collection install for setup.

### Ansible Execution Environment Migration
**Traditional Ansible Setup:**
```yaml
# Legacy requirements.txt
pyyaml
jinja2
cryptography
boto3
pymongo
mysql-connector-python

# Legacy playbook execution
ansible-playbook -i inventory site.yml
```

**Execution Environment Pattern:**
```dockerfile
# Dockerfile for Execution Environment
ARG EE_BASE_IMAGE=quay.io/ansible/ansible-runner:latest
FROM $EE_BASE_IMAGE

USER root

# Install system dependencies
RUN dnf -y install python3-pip git && \
    dnf clean all

# Install Python requirements
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# Install Ansible collections
COPY requirements.yml /tmp/requirements.yml
RUN ansible-galaxy collection install -r /tmp/requirements.yml --collections-path /usr/share/ansible/collections/

USER 1000
```

**Execution Environment Metadata:**
```yaml
# execution-environment.yml
---
version: 3

dependencies:
  galaxy: requirements.yml
  python: requirements.txt
  system: bindep.txt

images:
  base_image:
    name: quay.io/ansible/ansible-runner:latest

build_arg_defaults:
  ANSIBLE_CORE_VERSION: 2.12.0
```

**Modern Execution:**
```bash
# Building execution environment
ansible-builder build --tag my-ee:latest

# Running with execution environment
ansible-navigator run site.yml -i inventory \
  --execution-environment-image my-ee:latest
```

**Conversion Notes:** Containerize Ansible execution for consistency. Use ansible-navigator instead of ansible-playbook. Define dependencies in execution-environment.yml. Leverage container registries for distribution.

### Advanced Ansible Features Migration
**Basic Error Handling to Advanced:**
```yaml
# Legacy error handling
- name: Start service
  service:
    name: myapp
    state: started
  ignore_errors: yes

# Advanced error handling
- name: Start service with retry and recovery
  service:
    name: myapp
    state: started
  register: service_result
  retries: 3
  delay: 5
  until: service_result is succeeded
  rescue:
    - name: Check service status
      command: systemctl status myapp
      register: status_check
      
    - name: Restart service if failed
      service:
        name: myapp
        state: restarted
      when: "'failed' in status_check.stdout"
```

**Ansible Vault Evolution:**
```yaml
# Legacy vault usage
ansible-vault encrypt vars/secrets.yml
ansible-playbook --ask-vault-pass site.yml

# Modern vault with multiple IDs
ansible-vault encrypt --vault-id prod@prompt vars/prod-secrets.yml
ansible-vault encrypt --vault-id dev@~/.vault-dev vars/dev-secrets.yml

# Playbook with multiple vault IDs
ansible-playbook --vault-id prod@prompt --vault-id dev@~/.vault-dev site.yml
```

**Conversion Notes:** Implement proper error handling with rescue blocks. Use multiple vault IDs for environment separation. Leverage retries and until for reliability. Adopt block/rescue/always patterns for complex error handling.

## Best Practices and Patterns Summary

### Universal Conversion Principles
1. **Idempotency**: Ensure all converted tasks are idempotent
2. **Error Handling**: Implement proper error handling and recovery
3. **Variables**: Use Ansible variable naming conventions
4. **Security**: Leverage Ansible Vault for sensitive data
5. **Modularity**: Break complex tasks into reusable roles
6. **Testing**: Implement molecule testing for converted playbooks
7. **Documentation**: Document conversion decisions and dependencies

### Performance Optimization Patterns
```yaml
# Optimized task execution
- name: Efficient package installation
  package:
    name:
      - package1
      - package2
      - package3
    state: present
  # Instead of multiple individual tasks

# Parallel execution
- name: Configure multiple services
  service:
    name: "{{ item }}"
    state: started
    enabled: yes
  loop:
    - httpd
    - mysql
    - nginx
  async: 45
  poll: 5
```

### Security Hardening Patterns
```yaml
# Security-focused conversion
- name: Secure service configuration
  template:
    src: secure-config.j2
    dest: /etc/service/config
    owner: root
    group: root
    mode: '0600'
    backup: yes
  notify: restart service
  tags: security

- name: Validate configuration
  command: service-config-test /etc/service/config
  register: config_test
  failed_when: config_test.rc != 0
  changed_when: false
```

This comprehensive database provides detailed conversion patterns for migrating from various IaC tools to Ansible, including upgrade paths for Ansible itself. Each pattern includes practical examples, conversion notes, and best practices to ensure successful automation modernization. 