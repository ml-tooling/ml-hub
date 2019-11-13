"""
Web service that is supposed to be started via JupyterHub.
By this, the service has access to some information passed
by JupyterHub. For more information check out https://jupyterhub.readthedocs.io/en/stable/reference/services.html

Note: Logs probably don't appear in stdout, as the service is started as a subprocess by JupyterHub
"""

import os
import urllib3
import json
import time
import math
from threading import Thread
import logging

from tornado import web, ioloop
from jupyterhub.services.auth import HubAuthenticated

import docker.errors
from kubernetes import client, config, stream

from mlhubspawner import utils

# Environment variables passed by JupyterHub to the service
prefix = os.environ.get('JUPYTERHUB_SERVICE_PREFIX', '/')
service_url = os.getenv('JUPYTERHUB_SERVICE_URL')
jupyterhub_api_url = os.getenv('JUPYTERHUB_API_URL')
jupyterhub_api_token = os.getenv('JUPYTERHUB_API_TOKEN')

auth_header = {"Authorization": "token " + jupyterhub_api_token}

execution_mode = os.environ[utils.ENV_NAME_EXECUTION_MODE]

http = urllib3.PoolManager()

if execution_mode == utils.EXECUTION_MODE_LOCAL:
    docker_client_kwargs = json.loads(os.getenv("DOCKER_CLIENT_KWARGS"))
    docker_tls_kwargs = json.loads(os.getenv("DOCKER_TLS_CONFIG"))
    docker_client = utils.init_docker_client(docker_client_kwargs, docker_tls_kwargs)
elif execution_mode == utils.EXECUTION_MODE_KUBERNETES:
    # incluster config is the config given by a service account and it's role permissions
    config.load_incluster_config()
    kubernetes_client = client.CoreV1Api()

hub_name = utils.ENV_HUB_NAME
origin_label = "{}={}".format(utils.LABEL_MLHUB_ORIGIN, hub_name)
origin_label_filter = {"label": origin_label}

class UnifiedContainer():

    def __init__(self, resource):
        self.remove = lambda: logging.info("Remove property is not defined")
        self.resource = resource

    def with_id(self, id):
        self.id = id
        return self
    
    def with_name(self, name):
        self.name = name
        return self
    
    def with_labels(self, labels):
        self.labels = labels
        return self
    
    def with_remove(self, func):
        self.remove = lambda: func(self.resource)
        return self

def extract_container(resource):
    if execution_mode == utils.EXECUTION_MODE_LOCAL:
        unified_container = UnifiedContainer(resource) \
            .with_id(resource.id) \
            .with_name(resource.name) \
            .with_labels(resource.labels) \
            .with_remove(lambda container: container.remove(v=True, force=True))
    elif execution_mode == utils.EXECUTION_MODE_KUBERNETES:
        unified_container = UnifiedContainer(resource) \
            .with_id(resource.metadata.uid) \
            .with_name(resource.metadata.name) \
            .with_labels(resource.metadata.labels)

    if unified_container == None:
        raise UserWarning("The execution mode environment variable is not set correctly")

    return unified_container

def get_hub_docker_resources(docker_client_obj):
    return docker_client_obj.list(filters=origin_label_filter)

def get_hub_kubernetes_resources(namespaced_list_command, **kwargs):
    return namespaced_list_command(hub_name, **kwargs).items

def get_hub_containers():
    if execution_mode == utils.EXECUTION_MODE_LOCAL:
        hub_containers = get_hub_docker_resources(docker_client.containers)
    elif execution_mode == utils.EXECUTION_MODE_KUBERNETES:
        hub_containers = get_hub_kubernetes_resources(kubernetes_client.list_namespaced_pod, field_selector="status.phase=Running", label_selector=origin_label)
    
    return hub_containers

def remove_deleted_user_resources(existing_user_names: []):
    """Remove resources for which no user exists anymore by checking whether the label of user name occurs in the existing
    users list.

        Args:
            existing_user_names: list of user names that exist in the JupyterHub database

        Raises:
            UserWarning: in Kubernetes mode, the function does not work
    """

    if execution_mode == utils.EXECUTION_MODE_KUBERNETES:
        raise UserWarning("This method cannot be used in following hub execution mode " + execution_mode)

    def try_to_remove(remove_callback, resource) -> bool:
        """Call the remove callback until the call succeeds or until the number of tries is exceeded.

            Returns:
                bool: True if it could be removed, False if it was not removable within the number of tries
        """

        for i in range(3):
            try:
                remove_callback()
                return True
            except docker.errors.APIError:
                time.sleep(3)
        
        logging.info("Could not remove " + resource.name)
        return False


    def find_and_remove(docker_client_obj, get_labels, action_callback) -> None:
        """List all resources belonging to `docker_client_obj` which were created by MLHub.
        Then check the list of resources for resources that belong to a user who does not exist anymore 
        and call the remove function on them.

            Args:
                docker_client_obj: A Python docker client object, such as docker_client.containers, docker_client.networks,... It must implement a .list() function (check https://docker-py.readthedocs.io/en/stable/containers.html)
                get_labels (func): function to call on the docker resource to get the labels
                remove (func): function to call on the docker resource to remove it                
        """

        resources = get_hub_docker_resources(docker_client_obj)
        for resource in resources:
            user_label = get_labels(resource)[utils.LABEL_MLHUB_USER]
            if user_label not in existing_user_names:
                action_callback(resource)
                # successful = try_to_remove(remove, resource)
                    
    def container_action(container):
        try_to_remove(
            lambda: container.remove(v=True, force=True), 
            container
        )

    find_and_remove(
        docker_client.containers, 
        lambda res: res.labels, 
        container_action
    )

    def network_action(network):
        try:
            network.disconnect(hub_name)
        except docker.errors.APIError:
            pass
        
        try_to_remove(network.remove, network)

    find_and_remove(
        docker_client.networks, 
        lambda res: res.attrs["Labels"], 
        network_action
    )

    find_and_remove(
        docker_client.volumes,
        lambda res: res.attrs["Labels"],
        lambda res: try_to_remove(res.remove, res)
    )

def get_hub_usernames() -> []:
    r = http.request('GET', jupyterhub_api_url + "/users", 
        headers = {**auth_header}
    )

    data = json.loads(r.data.decode("utf-8"))
    existing_user_names = []
    for user in data:
        existing_user_names.append(user["name"])

    return existing_user_names

def remove_expired_workspaces(): 
    hub_containers = get_hub_containers()
    for container in hub_containers:
        unified_container = extract_container(container)
        lifetime_timestamp = utils.get_lifetime_timestamp(unified_container.labels)
        if lifetime_timestamp != 0:
            difference = math.ceil(lifetime_timestamp - time.time())
            # container lifetime is exceeded (remaining lifetime is negative)
            if difference < 0:
                user_name = unified_container.labels[utils.LABEL_MLHUB_USER]
                server_name = unified_container.labels[utils.LABEL_MLHUB_SERVER_NAME]
                url = jupyterhub_api_url + "/users/{user_name}/servers/{server_name}".format(user_name=user_name, server_name=server_name)
                r = http.request('DELETE', url,
                    body = json.dumps({"remove": True}).encode('utf-8'),
                    headers = {**auth_header}
                )

                if r.status == 202 or r.status == 204:
                    logging.info("Delete expired container " + unified_container.name)
                    unified_container.remove()

class CleanupUserResources(HubAuthenticated, web.RequestHandler):

    @web.authenticated
    def get(self):
        current_user = self.get_current_user()
        if current_user["admin"] is False:
            self.set_status(401)
            self.finish()
            return

        try:
            remove_deleted_user_resources(get_hub_usernames())
        except UserWarning as e:
            self.finish(str(e))

class CleanupExpiredContainers(HubAuthenticated, web.RequestHandler):

    @web.authenticated
    def get(self):
        current_user = self.get_current_user()
        if current_user["admin"] is False:
            self.set_status(401)
            self.finish()
            return

        remove_expired_workspaces()

app = web.Application([
    (r"{}users".format(prefix), CleanupUserResources),
    (r"{}expired".format(prefix), CleanupExpiredContainers)
])

service_port = int(service_url.split(":")[-1])
app.listen(service_port)

def internal_service_caller():
    clean_interval_seconds = int(os.getenv(utils.ENV_NAME_CLEANUP_INTERVAL_SECONDS))
    while True and clean_interval_seconds != -1:
        time.sleep(clean_interval_seconds)
        try:
            remove_deleted_user_resources(get_hub_usernames())
        except UserWarning:
            pass
        remove_expired_workspaces()

Thread(target=internal_service_caller).start()

ioloop.IOLoop.current().start()
