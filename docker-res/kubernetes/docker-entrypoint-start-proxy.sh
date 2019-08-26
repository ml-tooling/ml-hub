#!/bin/bash

printf "Starting nginx and configurable-http-proxy\n"

# get the incoming arguments and modify the port, as port 8000 is the port nginx is running on
modified_arguments=$(echo "$@" | sed -e "s/port=8000/port=8081/g")

# create / copy certificates
$_RESOURCES_PATH/scripts/setup_certs.sh

# Configure and start nginx

# TODO: make dependent on Kubernetes mode
sed -i 's/resolver 127.0.0.11/resolver 10.96.0.10/g' /etc/nginx/nginx.conf
sed -i "s/set \$service_suffix ''/set \$service_suffix .jhub.svc.cluster.local/g" /etc/nginx/nginx.conf

python $_RESOURCES_PATH/scripts/run_nginx.py

function start_http_proxy {
    echo "Start configurable-http-proxy"
    configurable-http-proxy $modified_arguments &
}

rm /usr/local/sbin/jupyterhub
# link the original library back to the temp location, as the started script has the paths cached and will use that
ln -s /usr/local/bin/jupyterhub /usr/local/sbin/jupyterhub

rm /usr/local/sbin/configurable-http-proxy
ln -s /usr/bin/configurable-http-proxy /usr/local/sbin/configurable-http-proxy

start_http_proxy

# Copied from: https://docs.docker.com/config/containers/multi-service_container/
# Naive check runs checks once a minute to see if either of the processes exited.
# This illustrates part of the heavy lifting you need to do if you want to run
# more than one service in a container. The container exits with an error
# if it detects that either of the processes has exited.
# Otherwise it loops forever, waking up every 60 seconds
while sleep 60; do
  ps aux |grep sshd |grep -q -v grep
  PROCESS_1_STATUS=$?

  ps aux |grep configurable-http-proxy |grep -q -v grep
  PROCESS_2_STATUS=$? 
  # If the greps above find anything, they exit with 0 status
  # If they are not both 0, then something is wrong
  if [ $PROCESS_2_STATUS -ne 0 ]; then
    echo "configurable-http-proxy stopped. Restart it..."
    start_http_proxy
  fi
done
