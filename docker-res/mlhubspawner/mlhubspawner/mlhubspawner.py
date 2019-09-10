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
import socket
import ipaddress
from traitlets import default, Unicode, List
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

LABEL_EXPIRATION_TIMESTAMP = 'expiration_timestamp_seconds'
LABEL_NVIDIA_VISIBLE_DEVICES = 'nvidia_visible_devices'

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

    workspace_images = List(
        trait = Unicode(),
        default_value = [],
        config = True,
        help = "Pre-defined workspace images"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Get the MLHub container name to be used as the DNS name for the spawned workspaces, so they can connect to the Hub even if the container is
        # removed and restarted
        client = self.highlevel_docker_client
        self.hub_name = client.containers.list(filters={"id": socket.gethostname()})[0].name # TODO: set default to mlhub?
        self.default_label = {"origin": self.hub_name}

        # Connect MLHub to the existing workspace networks (in case of removing / recreation). By this, the hub can connect to the existing
        # workspaces and does not have to restart them.
        try:
            network = client.networks.get(self.network_name)
            self.connect_hub_to_network(network)
        except:
            pass
    
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

        description_memory_limit = 'Minimum limit must be 4mb as required by Docker.'
        description_env = 'In the form env=value (one per line)'
        description_days_to_live = 'Number of days the container should live'
        description_gpus = 'Empty for no GPU-acess. A comma-separted list of numbers describe the indices of the accessible GPUs.'

        label_style = "width: 25%"
        input_style = "width: 75%"
        div_style = "margin-bottom: 16px"

        default_image = getattr(self, "image", "mltooling/ml-workspace:latest")

        # When GPus shall be used, change the default image to the default gpu image (if the user entered a different image, it is not changed), and show an info box
        # reminding the user of inserting a GPU-leveraging docker image
        show_gpu_info_box = "$('#gpu-info-box').css('display', 'block');"
        hide_gpu_info_box = "$('#gpu-info-box').css('display', 'none');"
        gpu_input_listener = "if(event.srcElement.value !== ''){{ {show_gpu_info_box} }}else{{ {hide_gpu_info_box} }}" \
            .format(
                show_gpu_info_box=show_gpu_info_box, 
                hide_gpu_info_box=hide_gpu_info_box
        )

        # Show / hide custom image input field when checkbox is clicked
        custom_image_listener = "if(event.target.checked){ $('#image-name').css('display', 'block'); $('.defined-images').css('display', 'none'); }else{ $('#image-name').css('display', 'none'); $('.defined-images').css('display', 'block'); }"

        # Create drop down menu with pre-defined custom images
        image_option_template = """
            <option value="{image}">{image}</option>
        """
        image_options = ""
        for image in self.workspace_images:
            image_options += image_option_template.format(image=image)

        images_template = """
            <select name="defined_image" class="defined-images" required autofocus>{image_options}</select>
        """.format(image_options=image_options)

        optional_label = "<span style=\"font-size: 12px; font-weight: 400;\">(optional)</span>"
        # template = super()._default_options_form()
        return """
            <div style="{div_style}">
                <label style="{label_style}" for="image">Docker Image</label>
                <div name="image">
                    <div style="margin-bottom: 4px">
                        <input style="margin-right: 8px;" type="checkbox" name="is_custom_image" onchange="{custom_image_listener}"></input>
                        <label style="font-weight: 400;" for="is_custom_image">Custom Image</label>
                    </div>
                    <input style="{input_style}; display: none;" name="custom_image" id="image-name" class="custom-image" placeholder="Custom Image"></input>
                    {images_template}
                </div>
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
                <label style="{label_style}" for="days_to_live" title="{description_days_to_live}">Days to live {optional_label}</label>
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
            images_template=images_template,
            custom_image_listener=custom_image_listener,
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

        if formdata.get('is_custom_image', ["off"])[0] == "on":
            options["image"] = formdata.get('custom_image', [None])[0]
        else:
            options["image"] = formdata.get('defined_image', [None])[0]

        options["cpu_limit"] = formdata.get('cpu_limit', [None])[0]
        options["mem_limit"] = formdata.get('mem_limit', [None])[0]
        options["is_mount_volume"] = formdata.get('is_mount_volume', ["off"])[0]
        options["days_to_live"] = formdata.get('days_to_live', [None])[0]

        env = {}
        env_lines = formdata.get('env', [''])

        for line in env_lines[0].splitlines():
            if line:
                key, value = line.split('=', 1)
                env[key.strip()] = value.strip()
        options['env'] = env

        options['gpus'] = formdata.get('gpus', [None])[0]

        self.new_creating = True

        return options

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
            # {username} and {servername} will be automatically replaced by DockerSpawner with the right values as in template_namespace
            #volumeName = self.name_template.format(prefix=self.prefix)
            self.volumes = {self.object_name: "/workspace"}

        extra_create_kwargs = {}
        # set default label 'origin' to know for sure which containers where started via the hub
        extra_create_kwargs['labels'] = self.default_label
        if self.user_options.get('days_to_live'):
            days_to_live_in_seconds = int(self.user_options.get('days_to_live')) * 24 * 60 * 60 # days * hours_per_day * minutes_per_hour * seconds_per_minute
            expiration_timestamp = time.time() + days_to_live_in_seconds
            extra_create_kwargs['labels'][LABEL_EXPIRATION_TIMESTAMP] =  str(expiration_timestamp)
        else:
            extra_create_kwargs['labels'][LABEL_EXPIRATION_TIMESTAMP] = str(0)

        if self.user_options.get('gpus'):
            extra_host_config['runtime'] = "nvidia"
            extra_create_kwargs['labels'][LABEL_NVIDIA_VISIBLE_DEVICES] = self.user_options.get('gpus')

        self.extra_host_config.update(extra_host_config)
        self.extra_create_kwargs.update(extra_create_kwargs)

        # Delete existing container when it is created via the options_form UI (to make sure that not an existing container is re-used when you actually want to create a new one)
        # reset the flag afterwards to prevent the container from being removed when just stopped
        if (hasattr(self, 'new_creating') and self.new_creating == True):
            self.remove = True
        res = yield super().start()
        self.remove = False
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
        # Clean up the network we created for the container when we started it
        # First, disconnect all containers from the network and then remove it.
        #network = self.highlevel_docker_client.networks.get(self.network_name)
        networks = self.highlevel_docker_client.networks.list(names=[self.network_name])
        if len(networks) == 1:
            network = networks[0]
            # network.containers / network.attrs do not list any containers while the cli does => looks like bug in Python client
            try:
                network.disconnect(self.hub_name)
            except:
                pass
            
            try:
                network.disconnect(self.object_name)
            except:
                pass
            
            network.remove()
        
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
        return client.networks.create(name, ipam=ipam_config, labels=self.default_label)
    
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
    
    def get_container_metadata(self) -> str:
        if self.container_id is None or self.container_id == '':
            return ""

        meta_information = []
        container_labels = self.get_labels()
        lifetime_timestamp = self.get_lifetime_timestamp(container_labels)
        if lifetime_timestamp != 0:
            difference_in_days = math.ceil((lifetime_timestamp - time.time())/60/60/24)
            meta_information.append("Expires: {}d".format(difference_in_days))
        
        nvidia_visible_devices = container_labels.get(LABEL_NVIDIA_VISIBLE_DEVICES, "")
        if nvidia_visible_devices != "":
            meta_information.append("GPUs: {}".format(nvidia_visible_devices))
        
        if len(meta_information) == 0:
            return ""
        
        return "({})".format(", ".join(meta_information))

    def get_lifetime_timestamp(self, labels: dict) -> float:
        return float(labels.get(LABEL_EXPIRATION_TIMESTAMP, '0'))

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

    # NOTE: overwrite method to fix an issue with the image splitting.
    # We create a PR with the fix for Dockerspawner and, if fixed, we can
    # remove this one here again
    @gen.coroutine
    def pull_image(self, image):
        """Pull the image, if needed
        - pulls it unconditionally if pull_policy == 'always'
        - otherwise, checks if it exists, and
          - raises if pull_policy == 'never'
          - pulls if pull_policy == 'ifnotpresent'
        """
        # docker wants to split repo:tag

        # the part split("/")[-1] allows having an image from a custom repo
        # with port but without tag. For example: my.docker.repo:51150/foo would not 
        # pass this test, resulting in image=my.docker.repo:51150/foo and tag=latest
        if ':' in image.split("/")[-1]:
            # rsplit splits from right to left, allowing to have a custom image repo with port
            repo, tag = image.rsplit(':', 1)
        else:
            repo = image
            tag = 'latest'

        if self.pull_policy.lower() == 'always':
            # always pull
            self.log.info("pulling %s", image)
            yield self.docker('pull', repo, tag)
            # done
            return
        try:
            # check if the image is present
            yield self.docker('inspect_image', image)
        except docker.errors.NotFound:
            if self.pull_policy == "never":
                # never pull, raise because there is no such image
                raise
            elif self.pull_policy == "ifnotpresent":
                # not present, pull it for the first time
                self.log.info("pulling image %s", image)
                yield self.docker('pull', repo, tag)