printf "Starting ML Hub\n"

# create / copy certificates
$_RESOURCES_PATH/scripts/setup_certs.sh

# Configure and start nginx
python $_RESOURCES_PATH/scripts/run_nginx.py

# Run ssh-bastion image entrypoint
nohup python $_RESOURCES_PATH/start_ssh.py &

# Start server
echo "Start server"
jupyterhub -f $_RESOURCES_PATH/jupyterhub_config.py
