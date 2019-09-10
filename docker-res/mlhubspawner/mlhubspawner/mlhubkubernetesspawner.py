"""Custom spawner for JupyterHub. 
It extends the KubeSpawner with following features:
- additional fields in spawn screen for named servers (set cpu limit, additional environment variables, ...)
- put each spawned container into its own subnet to separate them from each other. This is needed to protect the 'Tools' part
    of our custom workspace container
"""

from kubespawner import KubeSpawner
from kubernetes import client
from kubernetes.client.models import V1Service, V1ServiceSpec, V1ServicePort, V1ObjectMeta

import os
import socket
from traitlets import default, Unicode, List
from tornado import gen
import time, datetime
import math
import re

LABEL_EXPIRATION_TIMESTAMP = 'expiration_timestamp_seconds'
LABEL_NVIDIA_VISIBLE_DEVICES = 'nvidia_visible_devices'


class MLHubKubernetesSpawner(KubeSpawner):
    """Provides the possibility to spawn docker containers with specific options, such as resource limits (CPU and Memory), Environment Variables, ..."""

    workspace_images = List(
        trait = Unicode(),
        default_value = [],
        config = True,
        help = "Pre-defined workspace images"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.hub_name = os.getenv("MLHUB_NAME", "mlhub")
        self.default_label = {"origin": self.hub_name}   
    
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

        return options

    def get_env(self):
        env = super().get_env()
        
        if self.user_options.get('env'):
            env.update(self.user_options.get('env'))

        #if self.user_options.get('gpus'):
        #    env['NVIDIA_VISIBLE_DEVICES'] = self.user_options.get('gpus')

        if self.user_options.get('cpu_limit'):
            env["MAX_NUM_THREADS"] = self.user_options.get('cpu_limit')

        env['SSH_JUMPHOST_TARGET'] = self.pod_name

        return env

    @gen.coroutine
    def start(self):
        """Set custom configuration during start before calling the super.start method of Dockerspawner"""
        if self.user_options.get('image'):
            self.image = self.user_options.get('image')

        # Set request explicitly to 0, otherwise Kubernetes will set it to the same amount as limit
        # self.cpu_guarantee / self.mem_guarantee cannot be directly used, as they are of type ByteSpecification and, for example, 0G will be transformed to 0 which will not pass
        # the 'if cpu_guarantee' check (see https://github.com/jupyterhub/kubespawner/blob/8a6d66e04768565c0fc56c790a5fc42bfee634ec/kubespawner/objects.py#L279).
        # Hence, set it via extra_resource_guarantees.
        self.extra_resource_guarantees = {"cpu": 0, "memory": "0G"}
        if self.user_options.get('cpu_limit'):
            self.cpu_limit = float(self.user_options.get('cpu_limit'))

        if self.user_options.get('mem_limit'):
            memory = str(self.user_options.get('mem_limit'))
            self.mem_limit = memory.upper().replace("GB", "G").replace("KB", "K").replace("MB", "M").replace("TB", "T")

        #if self.user_options.get('is_mount_volume') == 'on':
            # {username} and {servername} will be automatically replaced by DockerSpawner with the right values as in template_namespace
        #    self.volumes = {'jhub-user-{username}{servername}': "/workspace"}

        # set default label 'origin' to know for sure which containers where started via the hub
        self.extra_labels['origin'] = self.hub_name
        self.extra_labels['pod_name'] = self.pod_name
        if self.user_options.get('days_to_live'):
            days_to_live_in_seconds = int(self.user_options.get('days_to_live')) * 24 * 60 * 60 # days * hours_per_day * minutes_per_hour * seconds_per_minute
            expiration_timestamp = time.time() + days_to_live_in_seconds
            self.extra_labels[LABEL_EXPIRATION_TIMESTAMP] =  str(expiration_timestamp)
        else:
            self.extra_labels[LABEL_EXPIRATION_TIMESTAMP] = str(0)

        #if self.user_options.get('gpus'):
        #    extra_host_config['runtime'] = "nvidia"
        #    self.extra_labels[LABEL_NVIDIA_VISIBLE_DEVICES] = self.user_options.get('gpus')

        res = yield super().start()

        # Create service for pod so that it can be routed via name
        service = V1Service(
            kind = 'Service',
            spec = V1ServiceSpec(
                type='ClusterIP',
                ports=[V1ServicePort(port=self.port, target_port=self.port)],
                selector={
                    'origin': self.extra_labels['origin'], 
                    'pod_name': self.extra_labels['pod_name']
                }
            ),
            metadata = V1ObjectMeta(
                name=self.pod_name,
                labels=self.extra_labels
            )
        )
        try:
            yield self.asynchronize(
                self.api.create_namespaced_service,
                namespace=self.namespace,
                body=service
            )
        except client.rest.ApiException as e:
            if e.status == 409:
                self.log.info('Service {} already existed. No need to re-create.'.format(self.pod_name))

        return res
    
    @gen.coroutine
    def stop(self, now=False):
        yield super().stop(now=now)

        yield self.asynchronize(
            self.api.delete_namespaced_service,
            name=self.pod_name,
            namespace=self.namespace
        )


    
    def get_container_metadata(self) -> str:
        if self.pod_name is None or self.pod_name == '':
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
            return self.pod_reflector.pods.get(self.pod_name, None).metadata.labels
        except:
            return {}
    
    @gen.coroutine
    def delete_if_exists(self, kind, safe_name, future):
        try:
            yield future
            self.log.info('Deleted %s/%s', kind, safe_name)
        except client.rest.ApiException as e:
            if e.status != 404:
                raise
            self.log.warn("Could not delete %s/%s: does not exist", kind, safe_name)
