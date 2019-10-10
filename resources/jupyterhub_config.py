"""
Basic configuration file for jupyterhub.
"""

import os

c = get_config()

# Override the Jupyterhub `normalize_username` function to remove problematic characters from the username - independent from the used authenticator.
# E.g. when the username is "lastname, firstname" and the comma and whitespace are not removed, they are encoded by the browser, which can lead to broken routing in our nginx proxy, 
# especially for the tools-part. 
# Everybody who starts the hub can override this behavior the same way we do in a mounted `jupyterhub_user_config.py` (Docker local) or via the `hub.extraConfig` (Kubernetes)
from jupyterhub.auth import Authenticator
original_normalize_username = Authenticator.normalize_username
def custom_normalize_username(self, username):
    username = original_normalize_username(self, username)
    for forbidden_username_char in [" ", ",", ";", "."]:
        username = username.replace(forbidden_username_char, "")
    return username
Authenticator.normalize_username = custom_normalize_username

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
# prevents directly opening your workspace after login
c.JupyterHub.redirect_to_server=False
c.JupyterHub.allow_named_servers = True

c.Spawner.port = int(os.getenv("DEFAULT_WORKSPACE_PORT", 8080))

# Set default environment variables used by our ml-workspace container
default_env = {"AUTHENTICATE_VIA_JUPYTER": "true", "SHUTDOWN_INACTIVE_KERNELS": "true"}
c.Spawner.environment = default_env

# Workaround to prevent api problems
c.Spawner.will_resume = True

# --- Spawner-specific ----
c.JupyterHub.spawner_class = 'mlhubspawner.MLHubDockerSpawner' # override in your config if you want to have a different spawner. If it is the or inherits from DockerSpawner, the c.DockerSpawner config can have an effect.

c.Spawner.image = "mltooling/ml-workspace:0.8.7"
c.Spawner.workspace_images = [c.Spawner.image, "mltooling/ml-workspace-gpu:0.8.7", "mltooling/ml-workspace-r:0.8.7", "mltooling/ml-workspace-spark:0.8.7"]
c.Spawner.notebook_dir = '/workspace'

# Connect containers to this Docker network
c.Spawner.use_internal_ip = True
c.Spawner.extra_host_config = { 'shm_size': '256m' }

c.Spawner.prefix = 'ws' 
c.Spawner.name_template = c.Spawner.prefix + '-{username}-hub{servername}' # override in your config when you want to have a different name schema. Also consider changing c.Authenticator.username_pattern and check the environment variables to permit ssh connection

# Don't remove containers once they are stopped - persist state
c.Spawner.remove_containers = False

c.Spawner.start_timeout = 600 # should remove errors related to pulling Docker images (see https://github.com/jupyterhub/dockerspawner/issues/293)
c.Spawner.http_timeout = 120

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

# In Kubernetes mode, load the Kubernetes Jupyterhub config that can be configured via a config.yaml.
# Those values will override the values set above, as it is loaded afterwards.
if os.environ['EXECUTION_MODE'] == "k8s":
    load_subconfig("{}/kubernetes/jupyterhub_chart_config.py".format(os.getenv("_RESOURCES_PATH")))

    c.JupyterHub.spawner_class = 'mlhubspawner.MLHubKubernetesSpawner'
    c.KubeSpawner.pod_name_template = c.Spawner.name_template

    from z2jh import set_config_if_not_none
    set_config_if_not_none(c.KubeSpawner, 'workspace_images', 'singleuser.workspaceImages')

    if not isinstance(c.KubeSpawner.environment, dict):
        c.KubeSpawner.environment = {}
    c.KubeSpawner.environment.update(default_env)

# Add nativeauthenticator-specific templates
if c.JupyterHub.authenticator_class == NATIVE_AUTHENTICATOR_CLASS:
    import nativeauthenticator
    # if template_paths is not set yet in user_config, it is of type traitlets.config.loader.LazyConfigValue; in other words, it was not initialized yet
    if not isinstance(c.JupyterHub.template_paths, list):
        c.JupyterHub.template_paths = []
    c.JupyterHub.template_paths.append("{}/templates/".format(os.path.dirname(nativeauthenticator.__file__)))
