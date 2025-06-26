# File: webapp/init.sls

{% set nginx_conf = "/etc/nginx/nginx.conf" %}
{% set web_user = "webadmin" %}

webapp_packages:
  pkg.installed:
    - names:
      - nginx
      - git
      - python3
      - python3-pip

webapp_user:
  user.present:
    - name: {{ web_user }}
    - home: /home/{{ web_user }}
    - shell: /bin/bash

webapp_app_dir:
  file.directory:
    - name: /srv/webapp
    - user: {{ web_user }}
    - group: {{ web_user }}
    - mode: 755

webapp_nginx_conf:
  file.managed:
    - name: {{ nginx_conf }}
    - source: salt://webapp/files/nginx.conf.j2
    - template: jinja
    - user: root
    - group: root
    - mode: 644

webapp_service:
  service.running:
    - name: nginx
    - enable: True
    - watch:
      - file: webapp_nginx_conf

webapp_env_file:
  file.managed:
    - name: /srv/webapp/.env
    - source: salt://webapp/files/env.j2
    - template: jinja
    - user: {{ web_user }}
    - group: {{ web_user }}

deploy_webapp_code:
  git.latest:
    - name: 'https://github.com/example-org/webapp.git'
    - target: /srv/webapp
    - user: {{ web_user }}
    - force_fetch: True
    - require:
      - pkg: webapp_packages

webapp_python_requirements:
  pip.installed:
    - requirements: /srv/webapp/requirements.txt
    - bin_env: /usr/bin/pip3
    - user: {{ web_user }}
    - require:
      - git: deploy_webapp_code
