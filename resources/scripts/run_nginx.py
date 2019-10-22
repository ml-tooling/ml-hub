#!/usr/bin/python

"""
Configure and start nginx service
"""

from subprocess import call, Popen
import os
import time

ENV_RESOURCES_PATH = os.environ["_RESOURCES_PATH"]
ENV_DEFAULT_WORKSPACE_PORT = os.environ["DEFAULT_WORKSPACE_PORT"]
ENV_HUB_NAME = os.environ.get("HUB_NAME", "hub")

NGINX_FILE = "/etc/nginx/nginx.conf"

# PREPARE SSL SERVING
# For HTTPS mode, switch the ports so that traffic its the multiplexer to differentiate between
# HTTPS and ssh traffic

# PREPARE SSL SERVING
UPSTREAM = "web"
SSL = ""
is_ssl_enabled = os.getenv("SSL_ENABLED", False)
if is_ssl_enabled is True \
                or is_ssl_enabled == "true" \
                or is_ssl_enabled == "on":
    ENV_SSL_RESOURCES_PATH =  os.getenv("_SSL_RESOURCES_PATH", "/resources/ssl")

    call("sed -i 's@#ssl_certificate_key@ssl_certificate_key " + ENV_SSL_RESOURCES_PATH + "/cert.key;@g' " + NGINX_FILE, shell=True)
    call("sed -i 's@#ssl_certificate@ssl_certificate " + ENV_SSL_RESOURCES_PATH + "/cert.crt;@g' " + NGINX_FILE, shell=True)
    UPSTREAM = "$upstream"
    SSL = " ssl"
else:
    print("Warning: If you want to use the SSH feature, you have to start the hub with ssl enabled.")
###

call("sed -i 's/{UPSTREAM}/" + UPSTREAM + "/g' " + NGINX_FILE, shell=True)
call("sed -i 's/{SSL}/" + SSL + "/g' " + NGINX_FILE, shell=True)
call("sed -i 's@{DEFAULT_WORKSPACE_PORT}@" + ENV_DEFAULT_WORKSPACE_PORT + "@g' " + NGINX_FILE, shell=True)
call("sed -i 's@{HUB_NAME}@" + ENV_HUB_NAME + "@g' " + NGINX_FILE, shell=True)

# start nginx
print("Start nginx")
call("nginx -c /etc/nginx/nginx.conf", shell=True)
