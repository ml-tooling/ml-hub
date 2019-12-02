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
import time
import re

from mlhubspawner import spawner_options, utils

LABEL_POD_NAME = "pod_name"
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

        self.hub_name = utils.ENV_HUB_NAME
        self.default_label = {utils.LABEL_MLHUB_ORIGIN: self.hub_name, utils.LABEL_MLHUB_USER: self.user.name, utils.LABEL_MLHUB_SERVER_NAME: self.name, LABEL_POD_NAME: self.pod_name}
        self.extra_labels.update(self.default_label)
    
    @default('options_form')
    def _options_form(self):
        """Return the spawner options screen"""

        # Only show spawner options for named servers (the default server should start with default values)
        if getattr(self, "name", "") == "":
            return ''

        return spawner_options.get_options_form(self)

    def options_from_form(self, formdata):
        """Extract the passed form data into the self.user_options variable."""
        
        return spawner_options.options_from_form(self, formdata)

    def get_env(self):
        env = super().get_env()
        
        if self.user_options.get('env'):
            env.update(self.user_options.get('env'))

        #if self.user_options.get('gpus'):
        #    env['NVIDIA_VISIBLE_DEVICES'] = self.user_options.get('gpus')

        if self.user_options.get(utils.OPTION_CPU_LIMIT):
            env[utils.OPTION_MAX_NUM_THREADS] = self.user_options.get(utils.OPTION_CPU_LIMIT)

        env[utils.OPTION_SSH_JUMPHOST_TARGET] = self.pod_name

        return env

    @gen.coroutine
    def start(self):
        """Set custom configuration during start before calling the super.start method of Dockerspawner"""

        self.saved_user_options = self.user_options

        if self.user_options.get(utils.OPTION_IMAGE):
            self.image = self.user_options.get(utils.OPTION_IMAGE)

        # Set request explicitly to 0, otherwise Kubernetes will set it to the same amount as limit
        # self.cpu_guarantee / self.mem_guarantee cannot be directly used, as they are of type ByteSpecification and, for example, 0G will be transformed to 0 which will not pass
        # the 'if cpu_guarantee' check (see https://github.com/jupyterhub/kubespawner/blob/8a6d66e04768565c0fc56c790a5fc42bfee634ec/kubespawner/objects.py#L279).
        # Hence, set it via extra_resource_guarantees.
        self.extra_resource_guarantees = {"cpu": 0, "memory": "0G"}
        if self.user_options.get(utils.OPTION_CPU_LIMIT):
            self.cpu_limit = float(self.user_options.get(utils.OPTION_CPU_LIMIT))

        if self.user_options.get(utils.OPTION_MEM_LIMIT):
            memory = str(self.user_options.get(utils.OPTION_MEM_LIMIT)) + "G"
            self.mem_limit = memory.upper().replace("GB", "G").replace("KB", "K").replace("MB", "M").replace("TB", "T")

        #if self.user_options.get('is_mount_volume') == 'on':
            # {username} and {servername} will be automatically replaced by DockerSpawner with the right values as in template_namespace
        #    self.volumes = {'jhub-user-{username}{servername}': "/workspace"}

        # set default label 'origin' to know for sure which containers where started via the hub
        #self.extra_labels['pod_name'] = self.pod_name
        if self.user_options.get(utils.OPTION_DAYS_TO_LIVE):
            days_to_live_in_seconds = int(self.user_options.get(utils.OPTION_DAYS_TO_LIVE)) * 24 * 60 * 60 # days * hours_per_day * minutes_per_hour * seconds_per_minute
            expiration_timestamp = time.time() + days_to_live_in_seconds
            self.extra_labels[utils.LABEL_EXPIRATION_TIMESTAMP] =  str(expiration_timestamp)
        else:
            self.extra_labels[utils.LABEL_EXPIRATION_TIMESTAMP] = str(0)

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
                    utils.LABEL_MLHUB_ORIGIN: self.extra_labels[utils.LABEL_MLHUB_ORIGIN], 
                    LABEL_POD_NAME: self.extra_labels[LABEL_POD_NAME]
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

        try:
            delete_options = client.V1DeleteOptions()
            delete_options.grace_period_seconds = self.delete_grace_period
            yield self.asynchronize(
                self.api.delete_namespaced_service,
                name=self.pod_name,
                namespace=self.namespace,
                body=delete_options
            )
        except:
            self.log.warn("Could not delete service with name {}".format(self.pod_name))


    def get_workspace_config(self) -> str:
        return utils.get_workspace_config(self)

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

    # get_state and load_state are functions used by Jupyterhub to save and load variables that shall be persisted even if the hub is removed and re-created
    # Override
    def get_state(self):
        state = super(MLHubKubernetesSpawner, self).get_state()
        state = utils.get_state(self, state)
        return state
    
    # Override
    def load_state(self, state):
        super(MLHubKubernetesSpawner, self).load_state(state)
        utils.load_state(self, state)
