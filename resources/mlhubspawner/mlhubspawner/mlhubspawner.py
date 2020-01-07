"""Custom spawner for JupyterHub. 
It extends the DockerSpawner with following features:
- additional fields in spawn screen for named servers (set cpu limit, additional environment variables, ...)
- put each spawned container into its own subnet to separate them from each other. This is needed to protect the 'Tools' part
    of our custom workspace container
"""

from dockerspawner import DockerSpawner

import docker
import docker.types
import docker.errors
from docker.utils import kwargs_from_env

import os
import subprocess
import socket
import ipaddress
from traitlets import default, Unicode, List
from tornado import gen
import psutil
import time
import re

from mlhubspawner import spawner_options, utils

# we create networks in the range of 172.33-255.0.0/24
# Docker by default uses the range 172.17-32.0.0, so we should be save using that range
INITIAL_CIDR_FIRST_OCTET = 172
INITIAL_CIDR_SECOND_OCTET = 33
INITIAL_CIDR = "{}.33.0.0/24".format(INITIAL_CIDR_FIRST_OCTET)

OPTION_SHM_SIZE = "shm_size"

def has_complete_network_information(network):
    """Convenient function to check whether the docker.Network object has all required properties.
    
    Args:
        network (docker.Network)

    Returns:
        bool: True if it has all properties, False otehrwise.
    """
    return network.attrs["IPAM"] and network.attrs["IPAM"]["Config"] \
        and len(network.attrs["IPAM"]["Config"]) > 0 \
        and network.attrs["IPAM"]["Config"][0]["Subnet"]


class MLHubDockerSpawner(DockerSpawner):
    """Provides the possibility to spawn docker containers with specific options, such as resource limits (CPU and Memory), Environment Variables, ..."""

    #hub_name = Unicode(config=True, help="Name of the hub container.")

    workspace_images = List(
        trait = Unicode(),
        default_value = [],
        config = True,
        help = "Pre-defined workspace images"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hub_name = utils.ENV_HUB_NAME
        self.default_labels = {utils.LABEL_MLHUB_ORIGIN: self.hub_name, utils.LABEL_MLHUB_USER: self.user.name, utils.LABEL_MLHUB_SERVER_NAME: self.name}
        # Get the MLHub container name to be used as the DNS name for the spawned workspaces, so they can connect to the Hub even if the container is
        # removed and restarted
        client = self.highlevel_docker_client

        # Connect MLHub to the existing workspace networks (in case of removing / recreation). By this, the hub can connect to the existing
        # workspaces and does not have to restart them.
        try:
            network = client.networks.get(self.network_name)
            self.connect_hub_to_network(network)
        except:
            pass

        # Get available resource information
        self.resource_information = {
            "cpu_count": psutil.cpu_count(),
            "memory_count_in_gb": round(psutil.virtual_memory().total/1024/1024/1024, 1),
            "gpu_count": self.get_gpu_info()
        }
    
    @property
    def highlevel_docker_client(self):
        """Create a highlevel docker client as 'self.client' is the low-level API client.

        Returns:
            docker.DockerClient
        """
        
        return utils.init_docker_client(self.client_kwargs, self.tls_config)

    @property
    def network_name(self):
        """
        self.network_name is used by DockerSpawner to connect the newly created container to the respective network
        """
        #return self.object_name
        return "{}-{}".format(self.hub_name, self.user.name)
    
    @default('options_form')
    def _options_form(self):
        """Return the spawner options screen"""

        # Only show spawner options for named servers (the default server should start with default values)
        if getattr(self, "name", "") == "":
            return ''

        return spawner_options.get_options_form_docker(self)

    def options_from_form(self, formdata):
        """Extract the passed form data into the self.user_options variable."""

        self.new_creating = True
        return spawner_options.options_from_form(self, formdata)

    def get_env(self):
        env = super().get_env()

        # Replace JupyterHub container id with the name for spawned workspaces, so that the workspaces can connect to the hub even if the hub was removed and recreated.
        # Otherwise, the workspaces would have the old container id that does not exist anymore in such a case.
        hostname_regex = re.compile("http(s)?://([a-zA-Z0-9]+):[0-9]{3,5}.*")
        jupyterhub_api_url = env.get('JUPYTERHUB_API_URL')
        if jupyterhub_api_url:
            hostname = hostname_regex.match(jupyterhub_api_url).group(2)
            env['JUPYTERHUB_API_URL'] = jupyterhub_api_url.replace(hostname, self.hub_name)
        jupyterhub_activity_url = env.get('JUPYTERHUB_ACTIVITY_URL')
        if jupyterhub_activity_url:
            hostname = hostname_regex.match(jupyterhub_activity_url).group(2)
            env['JUPYTERHUB_ACTIVITY_URL'] = jupyterhub_activity_url.replace(hostname, self.hub_name)
        
        if self.user_options.get('env'):
            env.update(self.user_options.get('env'))

        if self.user_options.get('gpus'):
            env['NVIDIA_VISIBLE_DEVICES'] = self.user_options.get('gpus')

        if self.user_options.get(utils.OPTION_CPU_LIMIT):
            env[utils.OPTION_MAX_NUM_THREADS] = self.user_options.get(utils.OPTION_CPU_LIMIT)

        env[utils.OPTION_SSH_JUMPHOST_TARGET] = self.object_name

        return env

    @gen.coroutine
    def start(self) -> (str, int):
        """Set custom configuration during start before calling the super.start method of Dockerspawner
        
        Returns:
            (str, int): container's ip address or '127.0.0.1', container's port
        """

        self.saved_user_options = self.user_options

        if self.user_options.get(utils.OPTION_IMAGE):
            self.image = self.user_options.get(utils.OPTION_IMAGE)

        extra_host_config = {}
        if self.user_options.get(utils.OPTION_CPU_LIMIT):
            # nano_cpus cannot be bigger than the number of CPUs of the machine (this method would currently not work in a cluster, as machines could be different than the machine where the runtime-manager and this code run.
            max_available_cpus = self.resource_information["cpu_count"]
            limited_cpus = min(
                int(self.user_options.get(utils.OPTION_CPU_LIMIT)), max_available_cpus)

            # the nano_cpu parameter of the Docker client expects an integer, not a float
            nano_cpus = int(limited_cpus * 1e9)
            extra_host_config['nano_cpus'] = nano_cpus
        if self.user_options.get(utils.OPTION_MEM_LIMIT):
            extra_host_config[utils.OPTION_MEM_LIMIT] = str(self.user_options.get(
                utils.OPTION_MEM_LIMIT)) + "gb"

        if self.user_options.get('is_mount_volume') == 'on':
            # {username} and {servername} will be automatically replaced by DockerSpawner with the right values as in template_namespace
            #volumeName = self.name_template.format(prefix=self.prefix)
            self.highlevel_docker_client.volumes.create(name=self.object_name, labels=self.default_labels)
            self.volumes = {self.object_name: "/workspace"}

        extra_create_kwargs = {}
        # set default label 'origin' to know for sure which containers where started via the hub
        extra_create_kwargs[utils.OPTION_LABELS] = self.default_labels
        if self.user_options.get(utils.OPTION_DAYS_TO_LIVE):
            days_to_live_in_seconds = int(self.user_options.get(utils.OPTION_DAYS_TO_LIVE)) * 24 * 60 * 60 # days * hours_per_day * minutes_per_hour * seconds_per_minute
            expiration_timestamp = time.time() + days_to_live_in_seconds
            extra_create_kwargs[utils.OPTION_LABELS][utils.LABEL_EXPIRATION_TIMESTAMP] =  str(expiration_timestamp)
        else:
            extra_create_kwargs[utils.OPTION_LABELS][utils.LABEL_EXPIRATION_TIMESTAMP] = str(0)

        if self.user_options.get(OPTION_SHM_SIZE):
            extra_host_config[OPTION_SHM_SIZE] = self.user_options.get('shm_size')

        if self.user_options.get('gpus'):
            extra_host_config['runtime'] = "nvidia"
            extra_create_kwargs[utils.OPTION_LABELS][utils.LABEL_NVIDIA_VISIBLE_DEVICES] = self.user_options.get('gpus')

        self.extra_host_config.update(extra_host_config)
        self.extra_create_kwargs.update(extra_create_kwargs)

        # Check whether the network still exists to which the container will try to connect
        try:
            self.highlevel_docker_client.networks.get(self.network_name)
        except docker.errors.NotFound:
            created_network = self.create_network(self.network_name)
            self.connect_hub_to_network(created_network)
        except docker.errors.APIError:
            self.log.error("Could not look up network {network_name}".format(network_name=self.network_name))

        # Delete existing container when it is created via the options_form UI (to make sure that not an existing container is re-used when you actually want to create a new one)
        # reset the flag afterwards to prevent the container from being removed when just stopped
        # Also make it deletable via the user_options (can be set via the POST API)
        if ((hasattr(self, 'new_creating') and self.new_creating == True) 
            or self.user_options.get("update", False)):
            self.remove = True
        res = yield super().start()
        self.remove = False
        self.new_creating = False
        return res

    @gen.coroutine
    def create_object(self):
        created_network = None
        try:
            created_network = self.create_network(self.network_name)
            self.connect_hub_to_network(created_network)
        except:
            self.log.error(
                "Could not create the network {network_name} and, thus, cannot create the container."
                    .format(network_name=self.network_name)
            )
            return
        
        obj = yield super().create_object()
        return obj
        
    @gen.coroutine
    def remove_object(self):
        yield super().remove_object()


    def create_network(self, name):
        """Create a new network to put the new container into it. 
        Containers are separated by networks to prevent them from seeing each other.
        Determine whether a new subnet has to be used. Otherwise, the default Docker subnet would be used
        and, as a result, the amount of networks that can be created is strongly limited.
        We create networks in the range of 172.33-255.0.0/24 whereby Docker by default uses the range 172.17-32.0.0
        See: https://stackoverflow.com/questions/41609998/how-to-increase-maximum-docker-network-on-one-server ; https://loomchild.net/2016/09/04/docker-can-create-only-31-networks-on-a-single-machine/

        Args:
            name (str): name of the network to be created

        Returns:
            docker.Network: the newly created network or the existing network with the given name

        """

        client = self.highlevel_docker_client
        networks = client.networks.list()
        highest_cidr = ipaddress.ip_network(INITIAL_CIDR)

        # determine subnet for the network to be created by finding the highest subnet so far.
        # E.g. when you have three subnets 172.33.1.0, 172.33.2.0, and 172.33.3.0, highest_cidr will be 172.33.3.0
        for network in networks:
            if network.name.lower() == name.lower():
                self.log.info("Network {} already exists".format(name))
                return network

            if (has_complete_network_information(network)):
                cidr = ipaddress.ip_network(
                    network.attrs["IPAM"]["Config"][0]["Subnet"])

                if cidr.network_address.packed[0] == INITIAL_CIDR_FIRST_OCTET \
                        and cidr.network_address.packed[1] >= INITIAL_CIDR_SECOND_OCTET:
                    if cidr > highest_cidr:
                        highest_cidr = cidr

        # take the highest cidr and add 256 bits, so that if the highest subnet was 172.33.2.0, the new subnet is 172.33.3.0
        next_cidr = ipaddress.ip_network(
            (highest_cidr.network_address + 256).exploded + "/24")
        if next_cidr.network_address.packed[0] > INITIAL_CIDR_FIRST_OCTET:
            raise Exception("No more possible subnet addresses exist")

        self.log.info("Create network {} with subnet {}".format(
            name, next_cidr.exploded))
        ipam_pool = docker.types.IPAMPool(subnet=next_cidr.exploded,
                                          gateway=(next_cidr.network_address + 1).exploded)
        ipam_config = docker.types.IPAMConfig(pool_configs=[ipam_pool])
        return client.networks.create(name, ipam=ipam_config, labels=self.default_labels)
    
    def connect_hub_to_network(self, network):
        try:
            network.connect(self.hub_name)
        except docker.errors.APIError as e:
            # In the case of an 403 error, JupyterHub is already in the network which is okay -> continue starting the new container
            # Example 403 error:
            # 403 Client Error: Forbidden ("endpoint with name mlhub already exists in network jupyter-admin")
            if e.status_code != 403:
                self.log.error(
                    "Could not connect mlhub to the network and, thus, cannot create the container.")
                return
    
    def get_workspace_config(self) -> str:
        return utils.get_workspace_config(self)

    def is_update_available(self):
        try:
            # compare the last parts of the images, so that also "mltooling/ml-workspace:0.8.7 = ml-workspace:0.8.7" would match
            config_image = self.image.split("/")[-1]
            workspace_image = self.highlevel_docker_client.containers.get(self.container_id).image.tags[0].split("/")[-1]

            return config_image != workspace_image
        except (docker.errors.NotFound, docker.errors.NullResource):
            return False

    def get_labels(self) -> dict:
        try:
            return self.highlevel_docker_client.containers.get(self.container_id).labels
        except:
            return {}

    # Override
    def template_namespace(self):
        template = super().template_namespace()
        if template["servername"] != "":
            template["servername"] = "-" + template["servername"]
        
        return template

    # get_state and load_state are functions used by Jupyterhub to save and load variables that shall be persisted even if the hub is removed and re-created
    # Override
    def get_state(self):
        state = super(MLHubDockerSpawner, self).get_state()
        state = utils.get_state(self, state)
        return state
    
    # Override
    def load_state(self, state):
        super(MLHubDockerSpawner, self).load_state(state)
        utils.load_state(self, state)

    def get_gpu_info(self) -> list:
        count_gpu = 0
        try:
            # NOTE: this approach currently only works for nvidia gpus.
            ps = subprocess.Popen(('find', '/proc/irq/', '-name', 'nvidia'), stdout=subprocess.PIPE)
            output = subprocess.check_output(('wc', '-l'), stdin=ps.stdout)
            ps.wait()
            count_gpu = int(output.decode("utf-8"))
        except:
            pass

        return count_gpu
