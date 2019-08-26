#!/bin/bash

printf "Starting ML Hub\n"

python $_RESOURCES_PATH/patch_hub_service.py

function start_ssh {
    echo "Start SSH Daemon service"
    # Run ssh-bastion image entrypoint
    nohup python $_RESOURCES_PATH/start_ssh.py &
}

function start_jupyterhub {
    # Start server
    echo "Start JupyterHub"
    config_file=$_RESOURCES_PATH/jupyterhub_config.py
    execution_mode=${EXECUTION_MODE:-local}
    if [ "$execution_mode" == "k8s" ]; then
      config_file=$_RESOURCES_PATH/kubernetes/jupyterhub_config.py
    fi
    jupyterhub -f $config_file &
}

rm /usr/local/sbin/jupyterhub
# link the original library back to the temp location, as the started script has the paths cached and will use that
ln -s /usr/local/bin/jupyterhub /usr/local/sbin/jupyterhub

rm /usr/local/sbin/configurable-http-proxy
ln -s /usr/bin/configurable-http-proxy /usr/local/sbin/configurable-http-proxy

# Preserve Kubernetes-specific environment variables for sshd process
echo "export KUBERNETES_SERVICE_HOST=$KUBERNETES_SERVICE_HOST" >> $SSHD_ENVIRONMENT_VARIABLES
echo "export KUBERNETES_SERVICE_PORT=$KUBERNETES_SERVICE_PORT" >> $SSHD_ENVIRONMENT_VARIABLES

start_ssh
start_jupyterhub

# Copied from: https://docs.docker.com/config/containers/multi-service_container/
# Naive check runs checks once a minute to see if either of the processes exited.
# This illustrates part of the heavy lifting you need to do if you want to run
# more than one service in a container. The container exits with an error
# if it detects that either of the processes has exited.
# Otherwise it loops forever, waking up every 60 seconds
while sleep 60; do
  ps aux |grep sshd |grep -q -v grep
  PROCESS_1_STATUS=$?

  ps aux |grep jupyterhub |grep -q -v grep
  PROCESS_2_STATUS=$?

  # If the greps above find anything, they exit with 0 status
  # If they are not both 0, then something is wrong
  if [ $PROCESS_1_STATUS -ne 0 ]; then
    echo "SSH Daemon stopped. Restart it..."
    start_ssh
  fi
  if [ $PROCESS_2_STATUS -ne 0 ]; then
    echo "JupyterHub stopped. Restart it..."
    start_jupyterhub
  fi
done