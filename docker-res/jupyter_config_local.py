"""
DockerSpawner configuration file for jupyterhub.
"""

import os

c = get_config()

#c.JupyterHub.ip = '0.0.0.0'
#c.DockerSpawner.host_ip = '0.0.0.0'
# User containers will access hub by container name on the Docker network
c.JupyterHub.hub_ip = 'mlhub' #'research-hub'
c.JupyterHub.port = 8000

#c.JupyterHub.hub_port = 8000
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

env = {}
kwargs_update = { 'command': spawn_cmd, 'labels': {}}
if os.getenv('STUDIO_ENDPOINT', None) is not None:
    kwargs_update['labels']['studio.origin'] = 'studio'
    env['STUDIO_ENDPOINT'] = os.getenv('STUDIO_ENDPOINT', '')
    env['STUDIO_API_TOKEN'] = os.getenv('STUDIO_API_TOKEN', '')

if env:
    c.Spawner.environment = env

c.DockerSpawner.extra_create_kwargs.update(kwargs_update)
# Connect containers to this Docker network
network_name = "jupyterhub"
c.DockerSpawner.use_internal_ip = True
c.DockerSpawner.network_name = network_name
# Pass the network name as argument to spawned containers
c.DockerSpawner.extra_host_config = { 'network_mode': network_name, 'shm_size': '256m' }
# Explicitly set notebook directory because we'll be mounting a host volume to
# it.  Most jupyter/docker-stacks *-notebook images run the Notebook server as
# user `jovyan`, and set the notebook directory to `/home/jovyan/work`.
# We follow the same convention.
#notebook_dir = os.environ.get('DOCKER_NOTEBOOK_DIR') or '/home/jovyan/work'
#notebook_dir = '/home/jovyan/'
#c.DockerSpawner.notebook_dir = notebook_dir
# Mount the real user's Docker volume on the host to the notebook user's
# notebook directory in the container
# c.DockerSpawner.volumes = { 'jupyterhub-user-{username}': notebook_dir }

ENV_SERVICE_SSL_ENABLED = os.getenv('SERVICE_SSL_ENABLED', False)
if ENV_SERVICE_SSL_ENABLED is True or ENV_SERVICE_SSL_ENABLED == 'true':
    c.DockerSpawner.volumes['studio-ssl'] = os.getenv('SERVICE_SSL_PATH', '/resources/ssl')

#c.DockerSpawner.extra_create_kwargs.update({ 'volume_driver': 'local' })
# Dont remove containers once they are stopped - persist state
c.DockerSpawner.remove_containers = False
# Workaround to prevent api problems
c.DockerSpawner.will_resume = True
# For debugging arguments passed to spawned containers
c.DockerSpawner.debug = True

# TLS config
#c.JupyterHub.port = 443
#c.JupyterHub.ssl_key = os.environ['SSL_KEY']
#c.JupyterHub.ssl_cert = os.environ['SSL_CERT']

# Authenticate users with GitHub OAuth
#c.JupyterHub.authenticator_class = 'oauthenticator.GitHubOAuthenticator'
#c.GitHubOAuthenticator.oauth_callback_url = os.environ['OAUTH_CALLBACK_URL']
#from oauthenticator.github import GitHubOAuthenticator
#c.JupyterHub.authenticator_class = GitHubOAuthenticator
c.JupyterHub.authenticator_class = 'nativeauthenticator.NativeAuthenticator'

c.JupyterHub.allow_named_servers = True

c.DockerSpawner.name_template = '{prefix}-{username}{servername}'


# c.JupyterHub.spawner_class = 'dockerspawner.DockerSpawner'
# c.JupyterHub.spawner_class = 'imagespawner.DockerImageChooserSpawner'

# The admin must pull these before they can be used.
c.DockerImageChooserSpawner.dockerimages = [
	'mltooling/ml-workspace',
	'docker.wdf.sap.corp:51150/com.sap.sapai.studio/studio-workspace'
]

c.JupyterHub.spawner_class = 'mlhubspawner.MLHubDockerSpawner'

c.DockerSpawner.http_timeout = 60

# Persist hub data on volume mounted inside container
#data_dir = os.environ.get('DATA_VOLUME_CONTAINER', '/data')

#c.JupyterHub.cookie_secret_file = os.path.join(data_dir,
#    'jupyterhub_cookie_secret')

#c.JupyterHub.db_url = 'postgresql://postgres:{password}@{host}/{db}'.format(
#    host=os.environ['POSTGRES_HOST'],
#    password=os.environ['POSTGRES_PASSWORD'],
#    db=os.environ['POSTGRES_DB'],
#)

# Whitlelist users and admins
# c.Authenticator.whitelist = whitelist = set()
# c.Authenticator.admin_users = admin = set()
# c.JupyterHub.admin_access = True
# pwd = os.path.dirname(__file__)
# with open(os.path.join(pwd, 'userlist')) as f:
#     for line in f:
#         if not line:
#             continue
#         parts = line.split()
#         name = parts[0]
#         whitelist.add(name)
#         if len(parts) > 1 and parts[1] == 'admin':
#             admin.add(name)
