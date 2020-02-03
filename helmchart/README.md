# Zero to MLHub with Kubernetes

This directory contains a *Helm chart* for a default configuration to use MLHub.

## MLHub Modifications

It is inspired and partially based on the great *[Zero to JupyterHub K8s](https://github.com/jupyterhub/zero-to-jupyterhub-k8s) project*.
However, we made some modifications for two reasons; first, to get it work with ml-hub and and [ml-workspace](https://github.com/ml-tooling/ml-workspace). Second, to simplify the setup. *Zero to Jupyterhub K8s* is very sophisticated but adds an extra layer of complexity by, for example, not directly enabling you to configure KubeSpawner as you are used to by Jupyterhub via it's `c.Spawner` config but via mixing it with infrastructure configuration in the same `values.yaml` file. They have a great documentation about pre-pulling images, auto-scaling the cluster etc. So if this simple version is not enough, we recommend to check out their project and documentation. 

Most prominent changes to the "original" project: 
- change of the command fields in hub and proxy yamls
- modifying ports to make tunnelling of ssh possible
- changes of default values, e.g. the used images
- changes of paths, e.g. the ssl secret mount path
- separated the deployment configuration and the configuration for JupyterHub & the Spawner
- removed a few Kubernetes resources such as the image puller etc.

We do not push the helm chart to a repository for now, so feel free to download it from the [mlhub releases page](https://github.com/ml-tooling/ml-hub/releases) or to create the package yourself via the `helm package` command.

You can then deploy the chart via `helm upgrade --install mlhub packaged-chart.tgz --namespace $namespace --values config.yaml --set-file userConfig=./jupyterhub_user_config.py`.
The `config.yaml` can be used to overrride default deployment values, the `userConfig` can be used to configure JupyterHub and the Spawner. 

For more details, check out the main [readme](https://github.com/ml-tooling/ml-hub).

## Config

You find the default values for the deployment in the *mlhub/values.yaml* file. Some values should be self-explanatory; if not we encourage you to have a look at the chart files or at the *[Zero to JupyterHub K8s](https://github.com/jupyterhub/zero-to-jupyterhub-k8s)* documentation, on which our setup is based.
