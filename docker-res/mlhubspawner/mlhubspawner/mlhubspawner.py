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
import ipaddress
from traitlets import (default)
from tornado import gen
import multiprocessing
import time, datetime
import math
import re

# we create networks in the range of 172.33-255.0.0/24
# Docker by default uses the range 172.17-32.0.0, so we should be save using that range
INITIAL_CIDR_FIRST_OCTET = 172
INITIAL_CIDR_SECOND_OCTET = 33
INITIAL_CIDR = "{}.33.0.0/24".format(INITIAL_CIDR_FIRST_OCTET)

MLHUB_NAME = os.getenv("MLHUB_NAME", "mlhub")

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

    @property
    def highlevel_docker_client(self):
        """Create a highlevel docker client as 'self.client' is the low-level API client.
        The configuration is done the same way DockerSpawner initializes the low-level API client.

        Returns:
            docker.DockerClient
        """

        kwargs = {"version": "auto"}
        if self.tls_config:
            kwargs["tls"] = docker.tls.TLSConfig(**self.tls_config)
        kwargs.update(kwargs_from_env())
        kwargs.update(self.client_kwargs)
        return docker.DockerClient(**kwargs)
    
    @default('options_form')
    def _options_form(self):
        """Return the spawner options screen"""

        # Only show spawner options for named servers (the default server should start with default values)
        if getattr(self, "name", "") == "":
            return ''

        description_memory_limit = 'Minimum limit must be 4mb as required by Docker.'
        description_env = 'In the form env=value (one per line)'
        description_days_to_live = 'Number of days the container should live'
        description_gpus = 'Empty for no GPU-acess. A comma-separted list of numbers describe the indices of the accessible GPUs.'

        label_style = "width: 25%"
        input_style = "width: 75%"
        div_style = "margin-bottom: 16px"

        default_image = getattr(self, "image", "mltooling/ml-workspace:latest")
        default_image_parts = default_image.split(":")
        default_image_gpu = default_image_parts[0]
        if len(default_image_parts) == 2:
            default_image_gpu = default_image_gpu + "-gpu:" + default_image_parts[1]
        
        # When GPus shall be used, change the default image to the default gpu image (if the user entered a different image, it is not changed), and show an info box
        # reminding the user of inserting a GPU-leveraging docker image
        gpu_input_listener = "if(event.srcElement.value !== ''){{$('#gpu-info-box').css('display', 'block'); if($('#image-name').val() === '{default_image}'){{$('#image-name').val('{default_image_gpu}');}}}}else{{$('#gpu-info-box').css('display', 'none'); if($('#image-name').val() === '{default_image_gpu}'){{$('#image-name').val('{default_image}');}}}}" \
            .format(default_image=default_image,
                default_image_gpu=default_image_gpu)
        optional_label = "<span style=\"font-size: 12px; font-weight: 400;\">(optional)</span>"
        # template = super()._default_options_form()
        return """
            <div style="{div_style}">
                <label style="{label_style}" for="image">Docker Image</label>
                <input style="{input_style}" name="image" id="image-name" value="{default_image}"></input>
            </div>
            <div style="{div_style}">
                <label style="{label_style}" for="cpu_limit">Number of CPUs {optional_label}</label>
                <input style="{input_style}" name="cpu_limit" placeholder="e.g. 8"></input>
            </div>
            <div style="{div_style}">
                <label style="{label_style}" for="mem_limit" title="{description_memory_limit}">Memory Limit {optional_label}</label>
                <input style="{input_style}" name="mem_limit" title="{description_memory_limit}" placeholder="e.g. 100mb, 8g, ..."></input>
            </div>
            <div style="{div_style}">
                <label style="{label_style}" for="env" title="{description_env}">Environment Variables {optional_label}</label>
                <textarea style="{input_style}" name="env" title="{description_env}" placeholder="FOO=BAR&#10;FOO2=BAR2"></textarea>
            </div>
            <div style="{div_style}">
                <input style="margin-right: 8px;" type="checkbox" name="is_mount_volume" checked></input>
                <label style="font-weight: 400;" for="is_mount_volume">Mount named volume to /workspace?</label>
            </div>
            <div style="{div_style}">
                <label style="{label_style}" for="days_to_live" title="{description_days_to_live}">Requested days to live {optional_label}</label>
                <input style="{input_style}" name="days_to_live" title="{description_days_to_live}" placeholder="e.g. 3"></input>
            </div>
            <div style="{div_style}">
                <label style="{label_style}" for="gpus" title="{description_gpus}">GPUs {optional_label}</label>
                <input style="{input_style}" name="gpus" title="{description_gpus}" placeholder="e.g. all, 0, 1, 2, ..." oninput="{gpu_input_listener}"></input>
                <div style="background-color: #ffa000; padding: 8px; margin-top: 4px; display: none; {input_style}" id="gpu-info-box">When using GPUs, make sure to use a GPU-supporting Docker image!</div>
            </div>
        """.format(
            div_style=div_style,
            label_style=label_style,
            input_style=input_style,
            default_image=default_image,
            default_image_gpu=default_image_gpu,
            optional_label=optional_label,
            gpu_input_listener=gpu_input_listener,
            description_memory_limit=description_memory_limit,
            description_env=description_env,
            description_days_to_live=description_days_to_live,
            description_gpus=description_gpus
        )

    def options_from_form(self, formdata):
        """Extract the passed form data into the self.user_options variable."""

        options = {}

        options["image"] = formdata.get('image', [None])[0]
        options["cpu_limit"] = formdata.get('cpu_limit', [None])[0]
        options["mem_limit"] = formdata.get('mem_limit', [None])[0]
        options["mount_volume"] = formdata.get('mount_volume', [False])[0]
        options["days_to_live"] = formdata.get('days_to_live', [None])[0]

        env = {}
        env_lines = formdata.get('env', [''])

        for line in env_lines[0].splitlines():
            if line:
                key, value = line.split('=', 1)
                env[key.strip()] = value.strip()
        options['env'] = env

        options['gpus'] = formdata.get('gpus', [None])[0]

        return options

    def get_env(self):
        env = super().get_env()

        # Replace JupyterHub container id with the name for spawned workspaces, so that the workspaces can connect to the hub even if the hub was removed and recreated.
        # Otherwise, the workspaces would have the old container id that does not exist anymore in such a case.
        hostname_regex = re.compile("http(s)?://([a-zA-Z0-9]+):[0-9]{3,5}.*")
        jupyterhub_api_url = env.get('JUPYTERHUB_API_URL')
        mlhub_container_name = MLHUB_NAME
        if jupyterhub_api_url:
            hostname = hostname_regex.match(jupyterhub_api_url).group(2)
            env['JUPYTERHUB_API_URL'] = jupyterhub_api_url.replace(hostname, mlhub_container_name)
        jupyterhub_activity_url = env.get('JUPYTERHUB_ACTIVITY_URL')
        if jupyterhub_activity_url:
            hostname = hostname_regex.match(jupyterhub_activity_url).group(2)
            env['JUPYTERHUB_ACTIVITY_URL'] = jupyterhub_activity_url.replace(hostname, mlhub_container_name)
        
        if self.user_options.get('env'):
            env.update(self.user_options.get('env'))

        if self.user_options.get('gpus'):
            env['NVIDIA_VISIBLE_DEVICES'] = self.user_options.get('gpus')

        if self.user_options.get('cpu_limit'):
            env["MAX_NUM_THREADS"] = self.user_options.get('cpu_limit')

        env['SSH_JUMPHOST_TARGET'] = self.object_name

        return env

    @gen.coroutine
    def start(self):
        """Set custom configuration during start before calling the super.start method of Dockerspawner"""

        if self.user_options.get('image'):
            self.image = self.user_options.get('image')

        extra_host_config = {}
        if self.user_options.get('cpu_limit'):
            # nano_cpus cannot be bigger than the number of CPUs of the machine (this method would currently not work in a cluster, as machines could be different than the machine where the runtime-manager and this code run.
            max_available_cpus = multiprocessing.cpu_count()
            limited_cpus = min(
                int(self.user_options.get('cpu_limit')), max_available_cpus)

            # the nano_cpu parameter of the Docker client expects an integer, not a float
            nano_cpus = int(limited_cpus * 1e9)
            extra_host_config['nano_cpus'] = nano_cpus
        if self.user_options.get('mem_limit'):
            extra_host_config['mem_limit'] = self.user_options.get(
                'mem_limit')

        if self.user_options.get('is_mount_volume') == 'on':
            server_name = getattr(self, "name", "")
            default_named_volume = 'jupyterhub-user-{username}' + server_name
            self.volumes = {default_named_volume: "/workspace"}

        extra_create_kwargs = {}
        # set default label 'origin' to know for sure which containers where started via the hub
        extra_create_kwargs['labels'] = {"origin": MLHUB_NAME}
        if self.user_options.get('days_to_live'):
            days_to_live_in_seconds = int(self.user_options.get('days_to_live')) * 24 * 60 * 60 # days * hours_per_day * minutes_per_hour * seconds_per_minute
            expiration_timestamp = time.time() + days_to_live_in_seconds
            extra_create_kwargs['labels']['expiration_timestamp_seconds'] =  str(expiration_timestamp)
        else:
            extra_create_kwargs['labels']['expiration_timestamp_seconds'] = str(0)

        if self.user_options.get('gpus'):
            extra_host_config['runtime'] = "nvidia"

        self.extra_host_config.update(extra_host_config)
        self.extra_create_kwargs.update(extra_create_kwargs)

        network_name = self.object_name
        created_network = None

        try:
            created_network = self.create_network(network_name)
            # set self.network_name to the name of the network so that JupyterHub connects the newly created container to the network
            self.network_name = network_name
        except:
            self.log.error(
                "Could not create the network {network_name} and, thus, cannot create the container."
                    .format(network_name=network_name)
            )
            return

        try:
            mlhub_container_id = os.getenv("HOSTNAME", MLHUB_NAME)
            created_network.connect(mlhub_container_id)
        except docker.errors.APIError as e:
            # In the case of an 403 error, JupyterHub is already in the network which is okay -> continue starting the new container
            # Example 403 error:
            # 403 Client Error: Forbidden ("endpoint with name mlhub already exists in network jupyter-admin")
            if e.status_code != 403:
                self.log.error(
                    "Could not connect mlhub to the network and, thus, cannot create the container.")
                return

        # set the remove flag to trigger the remove object logic in super class to delete the container if it already exists.
        # reset the flag afterwards to prevent the container from being removed when just stopped
        self.remvove = True
        res = yield super().start()
        self.remove = False
        return res

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
        return client.networks.create(name, ipam=ipam_config)

    def get_lifetime_timestamp(self):
        if self.container_id is None or self.container_id == '':
            return None
        
        try:
            container_labels = self.highlevel_docker_client.containers.get(self.container_id).labels
            expiration_timestamp_seconds = float(container_labels.get('expiration_timestamp_seconds', '0'))
            if expiration_timestamp_seconds == 0:
                return None
            return expiration_timestamp_seconds
        except:
            return None
    
    def get_container_metadata(self):
        meta_string = ""
        lifetime_timestamp = self.get_lifetime_timestamp()
        if lifetime_timestamp is not None:
            difference_in_days = math.ceil((lifetime_timestamp - time.time())/60/60/24)
            meta_string = "(Expires: {}d)".format(difference_in_days)

        return meta_string
