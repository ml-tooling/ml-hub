"""
DockerSpawner configuration file for jupyterhub.
"""

import os

c = get_config()

# User containers will access hub by container name on the Docker network
c.JupyterHub.hub_ip = '0.0.0.0' #'research-hub'
c.JupyterHub.port = 8000

# Persist hub data on volume mounted inside container
# TODO: should really be persisted?
data_dir = os.environ.get('DATA_VOLUME_CONTAINER', '/data')
if not os.path.exists(data_dir):
    os.makedirs(data_dir)
c.JupyterHub.cookie_secret_file = os.path.join(data_dir, 'jupyterhub_cookie_secret')
c.JupyterHub.db_url = os.path.join(data_dir, 'jupyterhub.sqlite')
c.JupyterHub.admin_access = True
c.JupyterHub.allow_named_servers = True

c.Spawner.port = 8090

# Set default environment variables used by our ml-workspace container
c.Spawner.environment = {"AUTHENTICATE_VIA_JUPYTER": "true", "SHUTDOWN_INACTIVE_KERNELS": "true"}

# Workaround to prevent api problems
c.Spawner.will_resume = True

# --- Spawner-specific ----
c.JupyterHub.spawner_class = 'mlhubspawner.MLHubDockerSpawner' # override in your config if you want to have a different spawner. If it is the or inherits from DockerSpawner, the c.DockerSpawner config can have an effect.

c.DockerSpawner.image = "mltooling/ml-workspace:0.5.6"
c.DockerSpawner.notebook_dir = '/workspace'

# Connect containers to this Docker network
c.DockerSpawner.use_internal_ip = True
c.DockerSpawner.extra_host_config = { 'shm_size': '256m' }

c.DockerSpawner.prefix = 'workspace' 
c.DockerSpawner.name_template = '{prefix}-{username}-hub{servername}' # override in your config when you want to have a different name schema. Also consider changing c.Authenticator.username_pattern and check the environment variables to permit ssh connection

# Don't remove containers once they are stopped - persist state
c.DockerSpawner.remove_containers = False

c.DockerSpawner.start_timeout = 600 # should remove errors related to pulling Docker images (see https://github.com/jupyterhub/dockerspawner/issues/293)
c.DockerSpawner.http_timeout = 60

# --- Authenticator ---
c.Authenticator.admin_users = {"admin"} # override in your config when needed, for example if you use a different authenticator (e.g. set Github username if you use GithubAuthenticator)
# Forbid user names that could collide with a named server (check ) to prevent security & routing problems
c.Authenticator.username_pattern = '^((?!-hub).)*$'

NATIVE_AUTHENTICATOR_CLASS = 'nativeauthenticator.NativeAuthenticator'
c.JupyterHub.authenticator_class = NATIVE_AUTHENTICATOR_CLASS # override in your config if you want to use a different authenticator

# --- Load user config ---
# Allow passing an additional config upon mlhub container startup.
# Enables the user to override all configurations occurring above the load_subconfig command; be careful to not break anything ;)
# An empty config file already exists in case the user does not mount another config file.
# The extra config could look like:
    # jupyterhub_user_config.py
    # > c = get_config()
    # > c.DockerSpawner.extra_create_kwargs.update({'labels': {'foo': 'bar'}})
# See https://traitlets.readthedocs.io/en/stable/config.html#configuration-files-inheritance
load_subconfig("{}/jupyterhub_user_config.py".format(os.getenv("_RESOURCES_PATH")))

# Add nativeauthenticator-specific templates
if c.JupyterHub.authenticator_class == NATIVE_AUTHENTICATOR_CLASS:
    import nativeauthenticator
    # if template_paths is not set yet in user_config, it is of type traitlets.config.loader.LazyConfigValue; in other words, it was not initialized yet
    if not isinstance(c.JupyterHub.template_paths, list):
        c.JupyterHub.template_paths = []
    c.JupyterHub.template_paths.append("{}/templates/".format(os.path.dirname(nativeauthenticator.__file__)))
