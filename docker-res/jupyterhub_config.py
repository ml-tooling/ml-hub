"""
DockerSpawner configuration file for jupyterhub.
"""

import os

c = get_config()

# User containers will access hub by container name on the Docker network
c.JupyterHub.hub_ip = '0.0.0.0' #'research-hub'
c.JupyterHub.port = 8000

c.Spawner.port = 8090
c.Authenticator.admin_users = {"admin"}
c.JupyterHub.admin_access = True
c.LocalAuthenticator.create_system_users = True
c.LocalAuthenticator.add_user_cmd = ['useradd', '-p', '$1$Lbk613af$d6FXfrpuQYTAkrxCFD9sS.']

notebook_dir = '/workspace'
c.DockerSpawner.notebook_dir = notebook_dir

c.DockerSpawner.image = "mltooling/ml-workspace:0.3.6-SNAPSHOT"

c.Spawner.cmd = "python /resources/run.py"
spawn_cmd = ['--NotebookApp.allow_root=True', '--NotebookApp.iopub_data_rate_limit=2147483647', '--NotebookApp.allow_origin="*"']

kwargs_update = { 'command': spawn_cmd, 'labels': {}}

c.DockerSpawner.extra_create_kwargs.update(kwargs_update)
# Connect containers to this Docker network
c.DockerSpawner.use_internal_ip = True
c.DockerSpawner.extra_host_config = { 'shm_size': '256m' }

# Dont remove containers once they are stopped - persist state
c.DockerSpawner.remove_containers = True
# Workaround to prevent api problems
c.DockerSpawner.will_resume = True
# For debugging arguments passed to spawned containers
#c.DockerSpawner.debug = True

# Authenticate users with GitHub OAuth
#c.JupyterHub.authenticator_class = 'oauthenticator.GitHubOAuthenticator'
#c.GitHubOAuthenticator.oauth_callback_url = os.environ['OAUTH_CALLBACK_URL']
#from oauthenticator.github import GitHubOAuthenticator
#c.JupyterHub.authenticator_class = GitHubOAuthenticator
c.JupyterHub.authenticator_class = 'nativeauthenticator.NativeAuthenticator'

c.JupyterHub.allow_named_servers = True

c.DockerSpawner.name_template = '{prefix}-{username}{servername}'

c.JupyterHub.spawner_class = 'mlhubspawner.MLHubDockerSpawner'

c.DockerSpawner.http_timeout = 60

# Persist hub data on volume mounted inside container
#data_dir = os.environ.get('DATA_VOLUME_CONTAINER', '/data')

#c.JupyterHub.cookie_secret_file = os.path.join(data_dir,
#    'jupyterhub_cookie_secret')

# Allow passing an additional config upon mlhub container startup. 
# An empty config file already exists in case the user does not mount another config file.
# The extra config could look like:
    # jupyterhub_user_config.py
    # > c = get_config()
    # > c.DockerSpawner.extra_create_kwargs.update({'labels': {'foo': 'bar'}})
# See https://traitlets.readthedocs.io/en/stable/config.html#configuration-files-inheritance 
load_subconfig("{}/jupyterhub_user_config.py".format(os.getenv("_RESOURCES_PATH")))
