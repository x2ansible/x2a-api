"""
x2a Platform Test Codes

Comprehensive collection of infrastructure code samples for testing all x2a agents.
Provides realistic, validated code samples for each supported platform with varying
complexity levels and testing scenarios.

Platforms Supported:
- Chef: Cookbooks, recipes, resources, templates
- Terraform: Providers, resources, modules, variables
- Puppet: Manifests, classes, modules, dependencies
- Salt: States, pillars, grains, formulas
- BladeLogic: CLI scripts, NSH scripts, deployment packages
- Mixed: Multi-platform environments and migrations

Each platform includes:
- Simple examples for basic testing
- Complex examples for comprehensive testing
- Edge cases for robustness testing
- Real-world scenarios for integration testing
"""

from typing import Dict, Any, List
from enum import Enum


class ComplexityLevel(Enum):
    """Code complexity levels for testing scenarios."""
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    ENTERPRISE = "enterprise"


class PlatformTestCodes:
    """
    Comprehensive platform-specific test code repository.
    
    Provides realistic infrastructure code samples for all supported platforms
    with varying complexity levels for comprehensive testing coverage.
    """
    
    # Chef Platform Test Codes
    CHEF_CODES = {
        ComplexityLevel.SIMPLE: '''
# x2a Chef Simple Test
cookbook_name = "x2a_simple_nginx"

package "nginx" do
  action :install
end

service "nginx" do
  action [:enable, :start]
end
'''.strip(),
        
        ComplexityLevel.MEDIUM: '''
# x2a Chef Medium Complexity Test
cookbook_name = "x2a_web_application"
cookbook_version = "2.1.0"

include_recipe "apt::default"

package "nginx" do
  action :install
end

service "nginx" do
  action [:enable, :start]
  supports :status => true, :restart => true, :reload => true
end

template "/etc/nginx/sites-available/default" do
  source "nginx_site.erb"
  variables({
    :server_name => node["app"]["server_name"],
    :document_root => node["app"]["document_root"],
    :port => node["app"]["port"]
  })
  notifies :reload, "service[nginx]", :delayed
end

directory "/var/www/html" do
  owner "www-data"
  group "www-data"
  mode "0755"
  recursive true
end
'''.strip(),
        
        ComplexityLevel.COMPLEX: '''
# x2a Chef Complex Enterprise Application
cookbook_name = "x2a_enterprise_stack"
cookbook_version = "3.0.0"
maintainer = "x2a Engineering Team"

include_recipe "apt::default"
include_recipe "nodejs::default"
include_recipe "database::mysql"

# Application user
user node["app"]["user"] do
  home node["app"]["home_dir"]
  shell "/bin/bash"
  system true
end

# Application directories
[node["app"]["log_dir"], node["app"]["pid_dir"], node["app"]["config_dir"]].each do |dir|
  directory dir do
    owner node["app"]["user"]
    group node["app"]["group"]
    mode "0755"
    recursive true
  end
end

# Database configuration
mysql_database node["app"]["database"]["name"] do
  connection(
    :host => node["app"]["database"]["host"],
    :username => "root",
    :password => node["mysql"]["server_root_password"]
  )
  action :create
end

# Application deployment
git node["app"]["deploy_dir"] do
  repository node["app"]["repository"]["url"]
  revision node["app"]["repository"]["branch"]
  user node["app"]["user"]
  group node["app"]["group"]
  action :sync
  notifies :restart, "service[app]", :delayed
end

# Configuration from encrypted data bag
app_secrets = Chef::EncryptedDataBagItem.load("secrets", "app")

template "#{node["app"]["config_dir"]}/app.conf" do
  source "app_config.erb"
  owner node["app"]["user"]
  group node["app"]["group"]
  mode "0600"
  variables({
    :database_password => app_secrets["database_password"],
    :api_key => app_secrets["api_key"],
    :environment => node.chef_environment
  })
  notifies :restart, "service[app]", :delayed
end

# Load balancer configuration
template "/etc/nginx/sites-available/app" do
  source "nginx_app.erb"
  variables({
    :upstream_servers => node["app"]["upstream_servers"],
    :ssl_certificate => node["app"]["ssl"]["certificate"],
    :ssl_key => node["app"]["ssl"]["private_key"]
  })
  notifies :reload, "service[nginx]", :delayed
end

# Monitoring and logging
template "/etc/logrotate.d/app" do
  source "logrotate_app.erb"
  mode "0644"
end

cron "app_backup" do
  minute "0"
  hour "2"
  command "#{node["app"]["scripts_dir"]}/backup.sh"
  user node["app"]["user"]
end
'''.strip()
    }
    
    # Terraform Platform Test Codes
    TERRAFORM_CODES = {
        ComplexityLevel.SIMPLE: '''
# x2a Terraform Simple Test
provider "aws" {
  region = "us-west-2"
}

resource "aws_instance" "x2a_test" {
  ami           = "ami-0c02fb55956c7d316"
  instance_type = "t3.micro"
  
  tags = {
    Name = "x2a-simple-test"
  }
}
'''.strip(),
        
        ComplexityLevel.MEDIUM: '''
# x2a Terraform Medium Complexity Test
terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "test"
}

variable "instance_count" {
  description = "Number of instances"
  type        = number
  default     = 2
}

data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]
  
  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  
  tags = {
    Name        = "x2a-${var.environment}-vpc"
    Environment = var.environment
  }
}

resource "aws_subnet" "public" {
  count = 2
  
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.${count.index + 1}.0/24"
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true
  
  tags = {
    Name = "x2a-${var.environment}-public-${count.index + 1}"
    Type = "public"
  }
}

resource "aws_instance" "web" {
  count = var.instance_count
  
  ami           = data.aws_ami.amazon_linux.id
  instance_type = "t3.micro"
  subnet_id     = aws_subnet.public[count.index % length(aws_subnet.public)].id
  
  vpc_security_group_ids = [aws_security_group.web.id]
  
  user_data = templatefile("${path.module}/user_data.sh", {
    environment = var.environment
  })
  
  tags = {
    Name        = "x2a-${var.environment}-web-${count.index + 1}"
    Environment = var.environment
  }
}

output "instance_ips" {
  description = "Public IP addresses of instances"
  value       = aws_instance.web[*].public_ip
}
'''.strip(),
        
        ComplexityLevel.COMPLEX: '''
# x2a Terraform Enterprise Infrastructure
terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }
  
  backend "s3" {
    bucket         = "x2a-terraform-state"
    key            = "infrastructure/terraform.tfstate"
    region         = "us-west-2"
    encrypt        = true
    dynamodb_table = "x2a-terraform-locks"
  }
}

# Variables
variable "environment" {
  description = "Environment name"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "application_config" {
  description = "Application configuration"
  type = object({
    name               = string
    version            = string
    min_capacity      = number
    max_capacity      = number
    desired_capacity  = number
    instance_type     = string
    enable_monitoring = bool
  })
}

# Locals
locals {
  common_tags = {
    Project     = "x2a"
    Environment = var.environment
    ManagedBy   = "terraform"
    Owner       = "x2a-engineering"
  }
  
  az_count = 3
  
  private_subnets = [
    for i in range(local.az_count) : "10.0.${i + 10}.0/24"
  ]
  
  public_subnets = [
    for i in range(local.az_count) : "10.0.${i + 1}.0/24"
  ]
}

# Data sources
data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

# VPC Module
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
  
  name = "${var.application_config.name}-${var.environment}"
  cidr = "10.0.0.0/16"
  
  azs             = slice(data.aws_availability_zones.available.names, 0, local.az_count)
  private_subnets = local.private_subnets
  public_subnets  = local.public_subnets
  
  enable_nat_gateway   = true
  enable_vpn_gateway   = false
  enable_dns_hostnames = true
  enable_dns_support   = true
  
  tags = local.common_tags
}

# Application Load Balancer
resource "aws_lb" "main" {
  name               = "${var.application_config.name}-${var.environment}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = module.vpc.public_subnets
  
  enable_deletion_protection = var.environment == "prod"
  
  access_logs {
    bucket  = aws_s3_bucket.access_logs.id
    prefix  = "alb"
    enabled = true
  }
  
  tags = local.common_tags
}

# Auto Scaling Group
resource "aws_autoscaling_group" "main" {
  name                = "${var.application_config.name}-${var.environment}-asg"
  vpc_zone_identifier = module.vpc.private_subnets
  target_group_arns   = [aws_lb_target_group.main.arn]
  health_check_type   = "ELB"
  
  min_size         = var.application_config.min_capacity
  max_size         = var.application_config.max_capacity
  desired_capacity = var.application_config.desired_capacity
  
  launch_template {
    id      = aws_launch_template.main.id
    version = "$Latest"
  }
  
  tag {
    key                 = "Name"
    value               = "${var.application_config.name}-${var.environment}-instance"
    propagate_at_launch = true
  }
  
  dynamic "tag" {
    for_each = local.common_tags
    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true
    }
  }
}

# RDS Database
module "rds" {
  source = "terraform-aws-modules/rds/aws"
  
  identifier = "${var.application_config.name}-${var.environment}-db"
  
  engine            = "mysql"
  engine_version    = "8.0"
  instance_class    = var.environment == "prod" ? "db.r5.large" : "db.t3.micro"
  allocated_storage = var.environment == "prod" ? 100 : 20
  
  db_name  = var.application_config.name
  username = "admin"
  password = random_password.db_password.result
  
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = module.vpc.database_subnet_group
  
  backup_retention_period = var.environment == "prod" ? 30 : 7
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:00-sun:05:00"
  
  monitoring_interval = var.application_config.enable_monitoring ? 60 : 0
  
  deletion_protection = var.environment == "prod"
  
  tags = local.common_tags
}

# Outputs
output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "alb_dns_name" {
  description = "Application Load Balancer DNS name"
  value       = aws_lb.main.dns_name
}

output "database_endpoint" {
  description = "RDS instance endpoint"
  value       = module.rds.db_instance_endpoint
  sensitive   = true
}
'''.strip()
    }
    
    # Puppet Platform Test Codes
    PUPPET_CODES = {
        ComplexityLevel.SIMPLE: '''
# x2a Puppet Simple Test
class x2a_nginx_simple {
  package { 'nginx':
    ensure => installed,
  }
  
  service { 'nginx':
    ensure => running,
    enable => true,
  }
}
'''.strip(),
        
        ComplexityLevel.MEDIUM: '''
# x2a Puppet Medium Complexity Test
class x2a_web_application (
  $server_name = 'localhost',
  $document_root = '/var/www/html',
  $port = 80,
  $ssl_enabled = false,
) {
  
  # Ensure packages are installed
  package { ['nginx', 'php-fpm']:
    ensure => installed,
  }
  
  # Configure nginx
  file { '/etc/nginx/sites-available/default':
    ensure  => file,
    content => template('x2a_web_application/nginx_site.erb'),
    require => Package['nginx'],
    notify  => Service['nginx'],
  }
  
  file { '/etc/nginx/sites-enabled/default':
    ensure => link,
    target => '/etc/nginx/sites-available/default',
    require => File['/etc/nginx/sites-available/default'],
    notify  => Service['nginx'],
  }
  
  # Create document root
  file { $document_root:
    ensure => directory,
    owner  => 'www-data',
    group  => 'www-data',
    mode   => '0755',
  }
  
  # Services
  service { 'nginx':
    ensure    => running,
    enable    => true,
    require   => Package['nginx'],
    subscribe => File['/etc/nginx/sites-available/default'],
  }
  
  service { 'php7.4-fpm':
    ensure  => running,
    enable  => true,
    require => Package['php-fpm'],
  }
  
  # Firewall rules
  if $ssl_enabled {
    firewall { '443 allow https':
      port   => 443,
      proto  => tcp,
      action => accept,
    }
  }
  
  firewall { "${port} allow http":
    port   => $port,
    proto  => tcp,
    action => accept,
  }
}
'''.strip(),
        
        ComplexityLevel.COMPLEX: '''
# x2a Puppet Enterprise Application Stack
class x2a_enterprise_stack (
  $environment = 'production',
  $database_config = {},
  $application_config = {},
  $monitoring_enabled = true,
  $backup_enabled = true,
) {
  
  # Validate parameters
  validate_hash($database_config)
  validate_hash($application_config)
  
  # Include required modules
  include stdlib
  include firewall
  include logrotate
  
  # Application user and groups
  group { $application_config['group']:
    ensure => present,
    gid    => $application_config['gid'],
  }
  
  user { $application_config['user']:
    ensure     => present,
    uid        => $application_config['uid'],
    gid        => $application_config['group'],
    home       => $application_config['home_dir'],
    shell      => '/bin/bash',
    managehome => true,
    require    => Group[$application_config['group']],
  }
  
  # Application directories
  $app_directories = [
    $application_config['home_dir'],
    $application_config['log_dir'],
    $application_config['config_dir'],
    $application_config['data_dir'],
    $application_config['backup_dir'],
  ]
  
  file { $app_directories:
    ensure  => directory,
    owner   => $application_config['user'],
    group   => $application_config['group'],
    mode    => '0755',
    require => User[$application_config['user']],
  }
  
  # Database setup
  class { 'mysql::server':
    root_password           => $database_config['root_password'],
    remove_default_accounts => true,
    restart                 => true,
  }
  
  mysql::db { $database_config['name']:
    user     => $database_config['user'],
    password => $database_config['password'],
    host     => $database_config['host'],
    grant    => ['SELECT', 'INSERT', 'UPDATE', 'DELETE'],
    require  => Class['mysql::server'],
  }
  
  # Application configuration
  file { "${application_config['config_dir']}/app.conf":
    ensure  => file,
    content => template('x2a_enterprise_stack/app_config.erb'),
    owner   => $application_config['user'],
    group   => $application_config['group'],
    mode    => '0600',
    require => File[$application_config['config_dir']],
    notify  => Service['app'],
  }
  
  # SSL certificates
  if $application_config['ssl_enabled'] {
    file { $application_config['ssl_cert_path']:
      ensure  => file,
      source  => "puppet:///modules/x2a_enterprise_stack/ssl/${::fqdn}.crt",
      owner   => 'root',
      group   => 'root',
      mode    => '0644',
      notify  => Service['nginx'],
    }
    
    file { $application_config['ssl_key_path']:
      ensure  => file,
      source  => "puppet:///modules/x2a_enterprise_stack/ssl/${::fqdn}.key",
      owner   => 'root',
      group   => 'root',
      mode    => '0600',
      notify  => Service['nginx'],
    }
  }
  
  # Load balancer configuration
  class { 'nginx':
    manage_repo => true,
    confd_purge => true,
  }
  
  nginx::resource::upstream { 'app_backend':
    members => $application_config['upstream_servers'],
  }
  
  nginx::resource::server { $application_config['server_name']:
    listen_port          => 80,
    server_name          => [$application_config['server_name']],
    use_default_location => false,
    ssl                  => $application_config['ssl_enabled'],
    ssl_cert             => $application_config['ssl_cert_path'],
    ssl_key              => $application_config['ssl_key_path'],
  }
  
  nginx::resource::location { 'app_proxy':
    server   => $application_config['server_name'],
    location => '/',
    proxy    => 'http://app_backend',
  }
  
  # Monitoring setup
  if $monitoring_enabled {
    class { 'prometheus::node_exporter':
      collectors_enable => ['systemd', 'filesystem', 'diskstats'],
    }
    
    # Log monitoring
    file { '/etc/filebeat/filebeat.yml':
      ensure  => file,
      content => template('x2a_enterprise_stack/filebeat.yml.erb'),
      require => Package['filebeat'],
      notify  => Service['filebeat'],
    }
  }
  
  # Backup configuration
  if $backup_enabled {
    cron { 'application_backup':
      command => "${application_config['scripts_dir']}/backup.sh",
      user    => $application_config['user'],
      hour    => 2,
      minute  => 0,
    }
    
    cron { 'database_backup':
      command => "/usr/local/bin/db_backup.sh ${database_config['name']}",
      user    => 'root',
      hour    => 1,
      minute  => 30,
    }
  }
  
  # Log rotation
  logrotate::rule { 'application_logs':
    path         => "${application_config['log_dir']}/*.log",
    rotate       => 30,
    rotate_every => 'day',
    compress     => true,
    delaycompress => true,
    missingok    => true,
    create       => true,
    create_mode  => '0644',
    create_owner => $application_config['user'],
    create_group => $application_config['group'],
  }
  
  # Service definition
  service { 'app':
    ensure    => running,
    enable    => true,
    hasstatus => true,
    require   => [
      File["${application_config['config_dir']}/app.conf"],
      Mysql::Db[$database_config['name']],
    ],
  }
}
'''.strip()
    }
    
    # Mixed Platform Test Codes
    MIXED_PLATFORM_CODES = {
        ComplexityLevel.MEDIUM: '''
# x2a Mixed Platform Infrastructure - Medium Complexity

# Chef Recipe for Application Setup
cookbook_name = "x2a_mixed_app"

package "docker" do
  action :install
end

service "docker" do
  action [:enable, :start]
end

# Terraform Infrastructure
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

resource "aws_instance" "app_server" {
  ami           = "ami-0c02fb55956c7d316"
  instance_type = "t3.medium"
  
  tags = {
    Name        = "x2a-mixed-app-server"
    Environment = "test"
    Platform    = "mixed"
  }
}

resource "aws_security_group" "app_sg" {
  name_description = "x2a mixed application security group"
  
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Puppet Manifest for System Configuration
class docker_config {
  package { 'docker-ce':
    ensure => installed,
  }
  
  service { 'docker':
    ensure => running,
    enable => true,
  }
  
  user { 'app':
    ensure => present,
    groups => ['docker'],
  }
}
'''.strip(),
        
        ComplexityLevel.COMPLEX: '''
# x2a Enterprise Mixed Platform Migration - Complex

# Chef Cookbook for Legacy Application
cookbook_name = "x2a_legacy_migration"
cookbook_version = "1.0.0"

include_recipe "apt::default"
include_recipe "java::default"

# Legacy application setup
package %w[tomcat8 apache2 mysql-server] do
  action :install
end

template "/etc/apache2/sites-available/legacy-app.conf" do
  source "apache_legacy.erb"
  variables({
    :server_name => node["legacy"]["server_name"],
    :tomcat_port => node["legacy"]["tomcat_port"]
  })
  notifies :reload, "service[apache2]"
end

# Database migration scripts
cookbook_file "/opt/migration/legacy_to_modern.sql" do
  source "migration_scripts/legacy_to_modern.sql"
  mode "0644"
  owner "root"
end

# Terraform Infrastructure for Modern Stack
terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
  }
}

# VPC for modern infrastructure
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
  
  name = "x2a-modern-infrastructure"
  cidr = "10.0.0.0/16"
  
  azs             = ["us-west-2a", "us-west-2b", "us-west-2c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
  
  enable_nat_gateway = true
  enable_vpn_gateway = false
  
  tags = {
    Terraform = "true"
    Environment = "migration"
    Project = "x2a-modernization"
  }
}

# EKS Cluster for containerized applications
module "eks" {
  source = "terraform-aws-modules/eks/aws"
  
  cluster_name    = "x2a-modern-cluster"
  cluster_version = "1.24"
  
  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets
  
  node_groups = {
    main = {
      desired_capacity = 3
      max_capacity     = 10
      min_capacity     = 1
      
      instance_types = ["t3.medium"]
      
      k8s_labels = {
        Environment = "migration"
        Application = "x2a-modern"
      }
    }
  }
}

# RDS for modern database
resource "aws_db_instance" "modern_db" {
  identifier = "x2a-modern-database"
  
  engine         = "postgres"
  engine_version = "14.6"
  instance_class = "db.t3.micro"
  
  allocated_storage     = 20
  max_allocated_storage = 100
  
  db_name  = "x2a_modern"
  username = "admin"
  password = random_password.db_password.result
  
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name
  
  backup_retention_period = 7
  backup_window          = "07:00-09:00"
  maintenance_window     = "sun:09:00-sun:11:00"
  
  skip_final_snapshot = true
  
  tags = {
    Name = "x2a-modern-database"
    Environment = "migration"
  }
}

# Puppet Manifests for System Standardization
class x2a_migration_infrastructure (
  $legacy_config = {},
  $modern_config = {},
  $migration_phase = 'preparation',
) {
  
  # Common security hardening
  class { 'ssh':
    permit_root_login => 'no',
    password_authentication => 'no',
    port => 2222,
  }
  
  # Monitoring for both legacy and modern systems
  class { 'prometheus::node_exporter':
    collectors_enable => [
      'systemd',
      'filesystem', 
      'diskstats',
      'netdev',
      'meminfo'
    ],
  }
  
  # Migration-specific configuration
  case $migration_phase {
    'preparation': {
      # Setup migration tools
      package { ['rsync', 'mysqldump', 'pg_dump']:
        ensure => installed,
      }
      
      file { '/opt/migration':
        ensure => directory,
        mode   => '0755',
      }
      
      file { '/opt/migration/scripts':
        ensure => directory,
        mode   => '0755',
      }
    }
    
    'execution': {
      # Data migration services
      service { 'x2a-data-migrator':
        ensure  => running,
        enable  => true,
        require => Package['x2a-migration-tools'],
      }
      
      # Traffic routing during migration
      file { '/etc/nginx/conf.d/migration_routing.conf':
        ensure  => file,
        content => template('x2a_migration/nginx_routing.erb'),
        notify  => Service['nginx'],
      }
    }
    
    'validation': {
      # Validation and rollback preparation
      cron { 'migration_validation':
        command => '/opt/migration/scripts/validate_migration.sh',
        user    => 'root',
        minute  => '*/15',
      }
      
      file { '/opt/migration/rollback.sh':
        ensure => file,
        source => 'puppet:///modules/x2a_migration/rollback.sh',
        mode   => '0755',
      }
    }
    
    'completion': {
      # Cleanup legacy systems
      service { ['tomcat8', 'apache2']:
        ensure => stopped,
        enable => false,
      }
      
      # Modern system validation
      exec { 'validate_modern_stack':
        command => '/opt/migration/scripts/validate_modern.sh',
        creates => '/opt/migration/.validation_complete',
      }
    }
  }
  
  # Health checks for migration monitoring
  file { '/usr/local/bin/migration_health_check.sh':
    ensure  => file,
    content => template('x2a_migration/health_check.erb'),
    mode    => '0755',
  }
  
  cron { 'migration_health_monitoring':
    command => '/usr/local/bin/migration_health_check.sh',
    user    => 'root',
    minute  => '*/5',
  }
}

# Salt States for Configuration Management
# /srv/salt/x2a/migration/init.sls
x2a_migration_packages:
  pkg.installed:
    - pkgs:
      - curl
      - jq
      - aws-cli
      - kubectl
      - helm

x2a_migration_user:
  user.present:
    - name: x2a-migrator
    - home: /home/x2a-migrator
    - shell: /bin/bash
    - groups:
      - docker
      - sudo

x2a_migration_config:
  file.managed:
    - name: /etc/x2a/migration.yaml
    - source: salt://x2a/migration/files/migration.yaml.jinja
    - template: jinja
    - user: root
    - group: root
    - mode: 644
    - makedirs: True

x2a_migration_service:
  service.running:
    - name: x2a-migration-orchestrator
    - enable: True
    - require:
      - file: x2a_migration_config
      - user: x2a_migration_user
'''.strip()
    }
    
    @classmethod
    def get_code(cls, platform: str, complexity: ComplexityLevel = ComplexityLevel.MEDIUM) -> str:
        """
        Get test code for specified platform and complexity.
        
        Args:
            platform: Platform name (chef, terraform, puppet, mixed)
            complexity: Complexity level
            
        Returns:
            Test code string
        """
        platform_lower = platform.lower()
        
        if platform_lower == "chef":
            return cls.CHEF_CODES.get(complexity, cls.CHEF_CODES[ComplexityLevel.MEDIUM])
        elif platform_lower == "terraform":
            return cls.TERRAFORM_CODES.get(complexity, cls.TERRAFORM_CODES[ComplexityLevel.MEDIUM])
        elif platform_lower == "puppet":
            return cls.PUPPET_CODES.get(complexity, cls.PUPPET_CODES[ComplexityLevel.MEDIUM])
        elif platform_lower in ["mixed", "mixed_platform"]:
            return cls.MIXED_PLATFORM_CODES.get(complexity, cls.MIXED_PLATFORM_CODES[ComplexityLevel.MEDIUM])
        else:
            # Default to Chef if platform not found
            return cls.CHEF_CODES[ComplexityLevel.MEDIUM]
    
    @classmethod
    def get_all_platforms(cls) -> List[str]:
        """Get list of all supported platforms."""
        return ["chef", "terraform", "puppet", "mixed_platform"]
    
    @classmethod
    def get_complexity_levels(cls) -> List[ComplexityLevel]:
        """Get list of all complexity levels."""
        return list(ComplexityLevel)


class WorkflowTestData:
    """Test data for workflow and integration testing."""
    
    WORKFLOW_SCENARIOS = {
        "simple_chef_analysis": {
            "input_code": PlatformTestCodes.get_code("chef", ComplexityLevel.SIMPLE),
            "expected_platform": "chef",
            "expected_complexity": "low",
            "expected_agents": ["orchestrator", "universal_extractor", "structured_analyzer", "synthesizer"]
        },
        
        "complex_terraform_analysis": {
            "input_code": PlatformTestCodes.get_code("terraform", ComplexityLevel.COMPLEX),
            "expected_platform": "terraform", 
            "expected_complexity": "high",
            "expected_agents": ["orchestrator", "universal_extractor", "structured_analyzer", "spec_generator", "storage_manager", "synthesizer"]
        },
        
        "mixed_platform_migration": {
            "input_code": PlatformTestCodes.get_code("mixed_platform", ComplexityLevel.COMPLEX),
            "expected_platforms": ["chef", "terraform", "puppet"],
            "expected_complexity": "high",
            "expected_agents": ["orchestrator", "universal_extractor", "structured_analyzer", "spec_generator", "storage_manager", "synthesizer"]
        }
    }
    
    @classmethod
    def get_workflow_scenario(cls, scenario_name: str) -> Dict[str, Any]:
        """Get workflow test scenario by name."""
        return cls.WORKFLOW_SCENARIOS.get(scenario_name, cls.WORKFLOW_SCENARIOS["simple_chef_analysis"])


class X2ATestCodes:
    """
    Convenience wrapper providing unified access to all x2a test codes.
    
    This is the main interface that other components should use to get test codes.
    """
    
    @staticmethod
    def get_platform_code(platform: str, complexity: str = "medium") -> str:
        """
        Get platform test code with string complexity.
        
        Args:
            platform: Platform name
            complexity: Complexity level as string
            
        Returns:
            Test code string
        """
        complexity_map = {
            "simple": ComplexityLevel.SIMPLE,
            "medium": ComplexityLevel.MEDIUM,
            "complex": ComplexityLevel.COMPLEX,
            "enterprise": ComplexityLevel.ENTERPRISE
        }
        
        complexity_level = complexity_map.get(complexity.lower(), ComplexityLevel.MEDIUM)
        return PlatformTestCodes.get_code(platform, complexity_level)
    
    @staticmethod
    def get_workflow_code(scenario: str) -> str:
        """Get code for workflow testing scenario."""
        workflow_data = WorkflowTestData.get_workflow_scenario(scenario)
        return workflow_data["input_code"]
    
    @staticmethod
    def get_all_test_codes() -> Dict[str, Dict[str, str]]:
        """Get all test codes organized by platform and complexity."""
        result = {}
        
        for platform in PlatformTestCodes.get_all_platforms():
            result[platform] = {}
            for complexity in PlatformTestCodes.get_complexity_levels():
                result[platform][complexity.value] = PlatformTestCodes.get_code(platform, complexity)
        
        return result
