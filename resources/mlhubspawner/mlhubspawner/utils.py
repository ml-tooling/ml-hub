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

LABEL_MLHUB_ORIGIN = "mlhub.origin"
LABEL_MLHUB_USER = "mlhub.user"
LABEL_MLHUB_SERVER_NAME = "mlhub.server_name"

ENV_NAME_EXECUTION_MODE = "EXECUTION_MODE"
EXECUTION_MODE_LOCAL = "local"
EXECUTION_MODE_KUBERNETES = "k8s"
ENV_NAME_CLEANUP_INTERVAL_SECONDS = "CLEANUP_INTERVAL_SECONDS"

ENV_HUB_NAME = os.getenv("HUB_NAME", "mlhub")

OPTION_LABELS = "labels"
OPTION_DAYS_TO_LIVE = "days_to_live"
OPTION_NANO_CPUS = "nano_cpus"
OPTION_CPU_LIMIT = "cpu_limit"
OPTION_MEM_LIMIT = "mem_limit"
OPTION_IMAGE = "image"
OPTION_SHM_SIZE = "shm_size"
OPTION_SSH_JUMPHOST_TARGET = "SSH_JUMPHOST_TARGET"
OPTION_MAX_NUM_THREADS = "MAX_NUM_THREADS"


def get_lifetime_timestamp(labels: dict) -> float:
    return float(labels.get(LABEL_EXPIRATION_TIMESTAMP, '0'))

def init_docker_client(client_kwargs: dict, tls_config: dict) -> docker.DockerClient:
    """Create a docker client. 
    The configuration is done the same way DockerSpawner initializes the low-level API client.

    Returns:
        docker.DockerClient, docker.APIClient
    """

    kwargs = {"version": "auto"}
    if tls_config:
        kwargs["tls"] = docker.tls.TLSConfig(**tls_config)
    kwargs.update(kwargs_from_env())
    if client_kwargs:
        kwargs.update(client_kwargs)
        
    return docker.DockerClient(**kwargs), docker.APIClient(**kwargs)

def get_state(spawner, state) -> dict:
    if hasattr(spawner, "saved_user_options"):
        state["saved_user_options"] = spawner.saved_user_options
    
    return state

def load_state(spawner, state):    
    if "saved_user_options" in state:
        spawner.saved_user_options = state.get("saved_user_options")

def get_workspace_config(spawner) -> str:
    workspace_config = {}
    if hasattr(spawner, "saved_user_options"):
        workspace_config = {**spawner.saved_user_options}

    # Add remaining lifetime information
    lifetime_timestamp = get_lifetime_timestamp(spawner.get_labels())
    if lifetime_timestamp != 0:
        difference_in_seconds = math.ceil(lifetime_timestamp - time.time())
        difference_in_days = math.ceil(difference_in_seconds/60/60/24)
        workspace_config.update({"remaining_lifetime_seconds": difference_in_seconds, "remaining_lifetime_days": difference_in_days})
    
    return json.dumps(workspace_config)
