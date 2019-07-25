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
c.JupyterHub.cookie_secret_file = os.path.join(data_dir, 'jupyterhub_cookie_secret')
c.JupyterHub.db_url = os.path.join(data_dir, 'jupyterhub.sqlite')
c.JupyterHub.admin_access = True
c.JupyterHub.allow_named_servers = True

c.Spawner.port = 8090

# TODO: check whether Spawner cmd can be removed as their are set as default in workspace
c.Spawner.cmd = "python /resources/run.py"

# Set default environment variables
c.Spawner.environment = {"AUTHENTICATE_VIA_JUPYTER": "true", "SHUTDOWN_INACTIVE_KERNELS": "true"}

#spawn_cmd = ['--NotebookApp.allow_root=True', '--NotebookApp.iopub_data_rate_limit=2147483647', '--NotebookApp.allow_origin="*"']

# TODO: check whether Spawner cmd can be removed as their are set as default in workspace
#kwargs_update = { 'command': spawn_cmd, 'labels': {}}
#c.DockerSpawner.extra_create_kwargs.update(kwargs_update)

c.JupyterHub.spawner_class = 'mlhubspawner.MLHubDockerSpawner'

c.DockerSpawner.image = "mltooling/ml-workspace:0.5.0"
c.DockerSpawner.notebook_dir = '/workspace'

# Connect containers to this Docker network
c.DockerSpawner.use_internal_ip = True
c.DockerSpawner.extra_host_config = { 'shm_size': '256m' }

c.DockerSpawner.prefix = 'workspace'
c.DockerSpawner.name_template = '{prefix}-{username}-hub{servername}'

# Don't remove containers once they are stopped - persist state
c.DockerSpawner.remove_containers = False
# Workaround to prevent api problems
c.DockerSpawner.will_resume = True

c.DockerSpawner.http_timeout = 60
# For debugging arguments passed to spawned containers
#c.DockerSpawner.debug = True

c.Authenticator.admin_users = {"admin"} # TODO: mark all variables that can be overridden
#c.LocalAuthenticator.create_system_users = True
#c.LocalAuthenticator.add_user_cmd = ['useradd', '-p', '$1$Lbk613af$d6FXfrpuQYTAkrxCFD9sS.']
# Forbid user names that could collide with a named server to prevent security & routing problems
c.Authenticator.username_pattern = '^((?!-hub).)*$'

NATIVE_AUTHENTICATOR_CLASS = 'nativeauthenticator.NativeAuthenticator'
c.JupyterHub.authenticator_class = NATIVE_AUTHENTICATOR_CLASS

# Allow passing an additional config upon mlhub container startup. 
# Enables the user to override all configurations occurring above the load_subconfig command.
# An empty config file already exists in case the user does not mount another config file.
# The extra config could look like:
    # jupyterhub_user_config.py
    # > c = get_config()
    # > c.DockerSpawner.extra_create_kwargs.update({'labels': {'foo': 'bar'}})
# See https://traitlets.readthedocs.io/en/stable/config.html#configuration-files-inheritance 
load_subconfig("{}/jupyterhub_user_config.py".format(os.getenv("_RESOURCES_PATH")))

def _get_path_to_library(module) -> str:
        """
        Get the path to a imported module. This way, the library can be found and loaded in unknown host environments.
        # Arguments
            module (module): Imported python module
        # Returns
            Full path to the provided module.
        """
        try:
            root_package = module.__name__.split(".")[0]
            return module.__file__.split(root_package)[0] + root_package
        except Exception as e:
            pass

# Add nativeauthenticator-specific templates
if c.JupyterHub.authenticator_class == NATIVE_AUTHENTICATOR_CLASS:
    import nativeauthenticator
    c.JupyterHub.template_paths = ["{}/templates/".format(_get_path_to_library(nativeauthenticator))]
