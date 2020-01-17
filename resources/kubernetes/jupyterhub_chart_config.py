from kubernetes import client
from yamlreader import yaml_load
from tornado.httpclient import AsyncHTTPClient
import os

### Begin config from chart
# Configure JupyterHub to use the curl backend for making HTTP requests,
# rather than the pure-python implementations. The default one starts
# being too slow to make a large number of requests to the proxy API
# at the rate required.
AsyncHTTPClient.configure("tornado.curl_httpclient.CurlAsyncHTTPClient")

# c.JupyterHub.spawner_class = 'kubespawner.KubeSpawner'

# Connect to a proxy running in a different pod
# The environment variables *_SERVICE_HOST/PORT are injected by Kubernetes automatically
c.ConfigurableHTTPProxy.api_url = 'http://{}:{}'.format(os.environ['PROXY_API_SERVICE_HOST'], int(os.environ['PROXY_API_SERVICE_PORT']))
c.ConfigurableHTTPProxy.should_start = False

c.JupyterHub.ip = os.environ['PROXY_PUBLIC_SERVICE_HOST']
c.JupyterHub.port = int(os.environ['PROXY_PUBLIC_SERVICE_PORT'])

c.JupyterHub.hub_connect_ip = os.environ['HUB_SERVICE_HOST']
c.JupyterHub.hub_connect_port = int(os.environ['HUB_SERVICE_PORT'])

# Do not shut down user pods when hub is restarted
c.JupyterHub.cleanup_servers = False

# Check that the proxy has routes appropriately setup
c.JupyterHub.last_activity_interval = 60

# Don't wait at all before redirecting a spawning user to the progress page
c.JupyterHub.tornado_settings = {
    'slow_spawn_timeout': 0,
}

# load the values from the mounted config-map
files = ["/etc/jupyterhub/config/values.yaml", "/etc/jupyterhub/secret/values.yaml"]
config = yaml_load(files)
c.JupyterHub.base_url = config["mlhub"]["baseUrl"]

# add dedicated-node toleration
for key in (
    'hub.jupyter.org/dedicated',
    # workaround GKE not supporting / in initial node taints
    'hub.jupyter.org_dedicated',
):
    c.Spawner.tolerations.append(
        dict(
            key=key,
            operator='Equal',
            value='user',
            effect='NoSchedule',
        )
    )

cloud_metadata = config['singleuser']['cloudMetadata']
if not cloud_metadata.get('enabled', False):
    # Use iptables to block access to cloud metadata by default
    network_tools_image_name = config['singleuser']['networkTools']['image']['name']
    network_tools_image_tag = config['singleuser']['networkTools']['image']['tag']
    ip_block_container = client.V1Container(
        name="block-cloud-metadata",
        image=f"{network_tools_image_name}:{network_tools_image_tag}",
        command=[
            'iptables',
            '-A', 'OUTPUT',
            '-d', cloud_metadata.get('ip', '169.254.169.254'),
            '-j', 'DROP'
        ],
        security_context=client.V1SecurityContext(
            privileged=True,
            run_as_user=0,
            capabilities=client.V1Capabilities(add=['NET_ADMIN'])
        )
    )

c.Spawner.init_containers.append(ip_block_container)

# implement common labels
# this duplicates the jupyterhub.commonLabels helper
if not isinstance(c.Spawner.common_labels, dict):
    c.Spawner.common_labels = {}

common_labels = c.Spawner.common_labels
common_labels['app'] = "mlhub"
if "nameOverride" in config:
    common_labels['app'] = config["nameOverride"]
else:
    common_labels['app'] = config["Chart"]["Name"]

common_labels['heritage'] = "mlhub"
chart_name = config['Chart']['Name']
chart_version = config['Chart']['Version']
if chart_name and chart_version:
    common_labels['chart'] = "{}-{}".format(
        chart_name, chart_version.replace('+', '_'),
    )
release = config['Release']['Name']
if release:
    common_labels['release'] = release

if config['mlhub']['debug']:
    c.JupyterHub.log_level = 'DEBUG'
    c.Spawner.debug = True


### End Chart config