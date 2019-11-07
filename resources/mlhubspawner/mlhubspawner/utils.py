"""
Shared util functions
"""

import os

import math
import time

import docker
from docker.utils import kwargs_from_env

import json

LABEL_NVIDIA_VISIBLE_DEVICES = 'nvidia_visible_devices'
LABEL_EXPIRATION_TIMESTAMP = 'expiration_timestamp_seconds'

LABEL_MLHUB_USER = "mlhub.user"

ENV_HUB_NAME = os.getenv("HUB_NAME", "mlhub")

def get_origin_label() -> tuple:
    """
    Returns:
        tuple (str, str): (key, value) for origin label
    """

    return "mlhub.origin", ENV_HUB_NAME

def get_container_metadata(spawner):
    meta_information = []
    container_labels = spawner.get_labels()
    lifetime_timestamp = spawner.get_lifetime_timestamp(container_labels)
    if lifetime_timestamp != 0:
        difference_in_days = math.ceil((lifetime_timestamp - time.time())/60/60/24)
        meta_information.append("Expires: {}d".format(difference_in_days))
    
    nvidia_visible_devices = container_labels.get(LABEL_NVIDIA_VISIBLE_DEVICES, "")
    if nvidia_visible_devices != "":
        meta_information.append("GPUs: {}".format(nvidia_visible_devices))
    
    if len(meta_information) == 0:
        return ""
    
    return "({})".format(", ".join(meta_information))

def init_docker_client(client_kwargs: dict, tls_config: dict) -> docker.DockerClient:
    """Create a docker client. 
    The configuration is done the same way DockerSpawner initializes the low-level API client.

    Returns:
        docker.DockerClient
    """

    kwargs = {"version": "auto"}
    if tls_config:
        kwargs["tls"] = docker.tls.TLSConfig(**tls_config)
    kwargs.update(kwargs_from_env())
    if client_kwargs:
        kwargs.update(client_kwargs)
        
    return docker.DockerClient(**kwargs)

def get_state(spawner, state) -> dict:
    if hasattr(spawner, "saved_user_options"):
        state["saved_user_options"] = spawner.saved_user_options
    
    return state

def load_state(spawner, state):    
    if "saved_user_options" in state:
        spawner.saved_user_options = state.get("saved_user_options")

def get_workspace_config(spawner) -> str:
    if not hasattr(spawner, "saved_user_options"):
        return "{}"
    
    return json.dumps(spawner.saved_user_options)
