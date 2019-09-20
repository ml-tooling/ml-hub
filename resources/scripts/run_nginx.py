#!/usr/bin/python

"""
Configure and start nginx service
"""

from subprocess import call, Popen
import os
import time

ENV_RESOURCES_PATH = os.environ["_RESOURCES_PATH"]
ENV_SSL_RESOURCES_PATH = os.environ["_SSL_RESOURCES_PATH"]
ENV_DEFAULT_WORKSPACE_PORT = os.environ["DEFAULT_WORKSPACE_PORT"]

NGINX_FILE = "/etc/nginx/nginx.conf"

# PREPARE SSL SERVING
# For HTTPS mode, switch the ports so that traffic its the multiplexer to differentiate between
# HTTPS and ssh traffic
call("sed -i 's@#ssl_certificate_key@ssl_certificate_key " + ENV_SSL_RESOURCES_PATH + "/cert.key;@g' " + NGINX_FILE, shell=True)
call("sed -i 's@#ssl_certificate@ssl_certificate " + ENV_SSL_RESOURCES_PATH + "/cert.crt;@g' " + NGINX_FILE, shell=True)
call("sed -i 's@{DEFAULT_WORKSPACE_PORT}@" + ENV_DEFAULT_WORKSPACE_PORT + "@g' " + NGINX_FILE, shell=True)
###

# start nginx
print("Start nginx")
call("nginx -c /etc/nginx/nginx.conf", shell=True)
