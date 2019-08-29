#!/bin/bash

printf "Starting ML Hub\n"

config_file=$_RESOURCES_PATH/jupyterhub_config.py
execution_mode=${EXECUTION_MODE:-local}
if [ "$execution_mode" == "k8s" ]; then
  config_file=$_RESOURCES_PATH/kubernetes/jupyterhub_config.py

  # make changes to nginx so that it works in Kubernetes as well
  # TODO: build into run_nginx.py script
  sed -i 's/resolver 127.0.0.11/resolver 10.96.0.10/g' /etc/nginx/nginx.conf
  sed -i "s/set \$service_suffix ''/set \$service_suffix .jhub.svc.cluster.local/g" /etc/nginx/nginx.conf

  # Preserve Kubernetes-specific environment variables for sshd process
  echo "export KUBERNETES_SERVICE_HOST=$KUBERNETES_SERVICE_HOST" >> $SSHD_ENVIRONMENT_VARIABLES
  echo "export KUBERNETES_SERVICE_PORT=$KUBERNETES_SERVICE_PORT" >> $SSHD_ENVIRONMENT_VARIABLES
fi

# It is possible to override the default sshd target with this command,
# e.g. if it runs in a different container
if [ -v "${SSHD_TARGET}" ]; then
  sed -i "s/127.0.0.1:22/${SSHD_TARGET}/g" /etc/nginx/nginx.conf
fi

# create / copy certificates
$_RESOURCES_PATH/scripts/setup_certs.sh

if [ "${START_NGINX}" == true ]; then
  # Configure and start nginx
  # TODO: restart nginx
  # TODO: make dependent on Kubernetes mode

  python $_RESOURCES_PATH/scripts/run_nginx.py
fi

function start_ssh {
    echo "Start SSH Daemon service"
    # Run ssh-bastion image entrypoint
    nohup python $_RESOURCES_PATH/start_ssh.py &
}

function start_jupyterhub {
    # Start server
    echo "Start JupyterHub"
    jupyterhub -f $config_file &
}

function start_http_proxy {
    echo "Start configurable-http-proxy"
    # $@ corresponds to the incoming script arguments
    configurable-http-proxy "$@" &
}

if [ "${START_SSH}" == true ]; then
  start_ssh
fi

if [ "${START_JHUB}" == true ]; then
  start_jupyterhub
fi

if [ "${START_CHP}" == true ]; then
  start_http_proxy
fi

# Copied from: https://docs.docker.com/config/containers/multi-service_container/
# Naive check runs checks once a minute to see if either of the processes exited.
# This illustrates part of the heavy lifting you need to do if you want to run
# more than one service in a container. The container exits with an error
# if it detects that either of the processes has exited.
# Otherwise it loops forever, waking up every 60 seconds
# If the greps find anything, they exit with 0 status (stored in $?)
while sleep 60; do
  if [ "${START_SSH}" == true ]; then
    ps aux |grep sshd |grep -q -v grep
    if [ $? -ne 0 ]; then
      echo "SSH Daemon stopped. Restart it..."
      start_ssh
    fi
  fi

  if [ "${START_JHUB}" == true ]; then
    ps aux |grep jupyterhub |grep -q -v grep
    if [ $? -ne 0 ]; then
      echo "JupyterHub stopped. Restart it..."
      start_jupyterhub
    fi
  fi

  if [ "${START_CHP}" == true ]; then
    ps aux |grep configurable-http-proxy |grep -q -v grep
    if [ $? -ne 0 ]; then
      echo "configurable-http-proxy stopped. Restart it..."
      start_http_proxy
    fi
  fi
done
