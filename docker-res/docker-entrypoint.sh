#!/bin/bash

printf "Starting ML Hub\n"

# create / copy certificates
$_RESOURCES_PATH/scripts/setup_certs.sh

# Configure and start nginx
python $_RESOURCES_PATH/scripts/run_nginx.py

function start_ssh {
    echo "Start SSH Daemon service"
    # Run ssh-bastion image entrypoint
    nohup python $_RESOURCES_PATH/start_ssh.py &
}

function start_jupyterhub {
    # Start server
    echo "Start JupyterHub"
    jupyterhub -f $_RESOURCES_PATH/jupyterhub_config.py &
}

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

