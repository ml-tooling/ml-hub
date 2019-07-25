# Kubespawner Docs: https://jupyterhub-kubespawner.readthedocs.io/en/latest/spawner.html#module-kubespawner.spawner

import subprocess
subprocess.call('apt-get update && apt-get install -y libcurl4-openssl-dev libssl-dev', shell=True)
subprocess.call("pip install jupyterhub-kubespawner", shell=True)
subprocess.call("pip install kubernetes==8.0.*", shell=True)
subprocess.call("pip install pycurl==7.43.0.*", shell=True)

#from tornado.httpclient import AsyncHTTPClient
#AsyncHTTPClient.configure("tornado.curl_httpclient.CurlAsyncHTTPClient")

c.JupyterHub.hub_connect_ip = 'docker.for.mac.localhost'

c.JupyterHub.spawner_class = 'kubespawner.KubeSpawner'
c.KubeSpawner.cpu_limit = 8
c.KubeSpawner.mem_limit = '100G'
# Set guarantees (= requests), otherwise they will be the same as the limit. Cannot be 0 or 0G as this is considered as 'False' in the code and, therefore, is not set
c.KubeSpawner.cpu_guarantee = 1
c.KubeSpawner.mem_guarantee = '1G'

c.KubeSpawner.image = "mltooling/ml-workspace:0.5.0"
c.Spawner.notebook_dir = '/workspace'
c.Spawner.http_timeout = 90

c.KubeSpawner.pod_name_template = 'workspace-{username}-hub{servername}'
# TODO: set kubernetes namespace?
# c.KubeSpawner.namespace = 'mlhub'