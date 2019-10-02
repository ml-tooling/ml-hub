<h1 align="center">
     ML Hub
    <br>
</h1>

<p align="center">
    <strong>Multi-user hub which spawns, manages, and proxies multiple workspace instances.</strong>
</p>

<p align="center">
    <a href="https://hub.docker.com/r/mltooling/ml-hub" title="Docker Image Version"><img src="https://images.microbadger.com/badges/version/mltooling/ml-hub.svg"></a>
    <a href="https://hub.docker.com/r/mltooling/ml-hub" title="Docker Pulls"><img src="https://img.shields.io/docker/pulls/mltooling/ml-hub.svg"></a>
    <a href="https://hub.docker.com/r/mltooling/ml-hub" title="Docker Image Metadata"><img src="https://images.microbadger.com/badges/image/mltooling/ml-hub.svg"></a>
    <a href="https://github.com/ml-tooling/ml-hub/blob/master/LICENSE" title="ML Hub License"><img src="https://img.shields.io/badge/License-Apache%202.0-green.svg"></a>
    <a href="https://gitter.im/ml-tooling/ml-hub" title="Chat on Gitter"><img src="https://badges.gitter.im/ml-tooling/ml-hub.svg"></a>
    <a href="https://twitter.com/mltooling" title="ML Tooling on Twitter"><img src="https://img.shields.io/twitter/follow/mltooling.svg?style=social"></a>
</p>

<p align="center">
  <a href="#highlights">Highlights</a> •
  <a href="#getting-started">Getting Started</a> •
  <a href="#features">Features & Screenshots</a> •
  <a href="#support">Support</a> •
  <a href="https://github.com/ml-tooling/ml-hub/issues/new?labels=bug&template=01_bug-report.md">Report a Bug</a> •
  <a href="#contribution">Contribution</a>
</p>

MLHub is based on [Jupyterhub](https://github.com/jupyterhub/jupyterhub). MLHub allows to create and manage multiple [workspaces](https://github.com/ml-tooling/ml-workspace), for example to distribute them to a group of people or within a team.

## Highlights

- 💫 Create, manage, and access Jupyter notebooks. Use it as an admin to distribute workspaces to other users, use it in self-service mode, or both.
- 🖊️ Set configuration parameters such as CPU-limits for started workspaces. 
- 🖥 Access additional tools within the started workspaces by having secured routes.
- 🎛 Tunnel SSH connections to workspace containers.

## Getting Started

### Prerequisites

- Docker
- Kubernetes (for Kubernetes modes)
- Helm (for easy deployment via our [helm chart](https://github.com/ml-tooling/ml-hub/releases/download/0.1.4/mlhub-chart-0.1.4.tgz))

Most parts will be identical to the configuration of Jupyterhub 1.0.0. One of the things that are different is that ssl will not be activated on proxy or hub-level, but on our nginx proxy.

### Start an instance via Docker

```bash
docker run \
    -p 8080 \
    --name mlhub \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v jupyterhub_data:/data \
    mltooling/ml-hub:latest
```

To persist the hub data, such as started workspaces and created users, mount a directory to `/data`.
A name (`--name`) must be set for the mlhub container, since we let the workspace container connect to the hub not via its docker id but its docker name. This way, the workspaces can still connect to the hub in case it was deleted and re-created (for example when the hub was updated).

For Kubernetes deployment, we forked and modified [zero-to-jupyterhub-k8s](https://github.com/jupyterhub/zero-to-jupyterhub-k8s) which you can find [here](https://github.com/ml-tooling/zero-to-mlhub-k8s).

### Configuration

In the default config, a user named `admin` can register and access the hub. If you use a different authenticator, you might want to set a different user as initial admin user as well.

#### Environment Variables

MLHub is based on [SSH Proxy](https://github.com/ml-tooling/ssh-proxy). Check out SSH Proxy for ssh-related configurations.
Here are the additional environment variables for the hub:
<table>
    <tr>
        <th>Variable</th>
        <th>Description</th>
        <th>Default</th>
    </tr>
    <tr>
        <td>SSL_ENABLED</td>
        <td>Enable SSL. If you don't provide an ssl certificate as described in <a href="https://github.com/ml-tooling/ml-hub#enable-sslhttps">Section "Enable SSL/HTTPS"</a>, certificates will be generated automatically. As this auto-generated certificate is not signed, you have to trust it in the browser. Without ssl enabled, ssh access won't work as the container uses a single port and has to tell https and ssh traffic apart.</td>
        <td>false</td>
    </tr>
    <tr>
        <td>START_SSH</td>
        <td>Start the sshd process which is used to tunnel ssh to the workspaces.</td>
        <td>true</td>
    </tr>
    <tr>
        <td>START_NGINX</td>
        <td>Whether or not to start the nginx proxy. If the Hub should be used without additional tool routing to workspaces, this could be disabled. SSH port 22 would need to be published separately then. This option is built-in to work with <a href="https://github.com/ml-tooling/zero-to-mlhub-k8s"> zero-to-mlhub-k8s</a>
        </td>
        <td>true</td>
    </tr>
    <tr>
        <td>START_JHUB</td>
        <td>Start the Jupyterhub hub. This option is built-in to work with
        <a href="https://github.com/ml-tooling/zero-to-mlhub-k8s"> zero-to-mlhub-k8s</a>, where the image is also used as the CHP image.</td>
        <td>true</td>
    </tr>
    <tr>
        <td>START_CHP</td>
        <td>Start the Jupyterhub proxy process separately (The hub should not start the proxy itself, which can be configured via the Jupyterhub config file. This option is built-in to work with <a href="https://github.com/ml-tooling/zero-to-mlhub-k8s"> zero-to-mlhub-k8s</a>, where the image is also used as the Configurable-Http-Proxy (CHP) image. Additional arguments to the chp-start command can be passed to the container by passing an environment variable ADDITIONAL_ARGS, e.g. --env ADDITIONAL_ARGS="--ip=0.0.0.0 --api-ip=0.0.0.0".</td>
        <td>false</td>
    </tr>
</table>

> ℹ️ _Via the START\_* environment variables, you can define what is started within the container. It's like this since the mlhub image is used in our Kubernetes setup for both, the hub and the proxy container. We did not want to break those functionalities into different images for now._

#### Jupyterhub Config

Jupyterhub itself is configured via a `config.py` file. In case of MLHub, a default config file is stored under `/resources/jupyterhub_config.py`. If you want to override settings or set extra ones, you can put another config file under `/resources/jupyterhub_user_config.py`. Following settings should probably not be overriden:
- `c.Spawner.environment` - we set default variables there. Instead of overriding it, you can add extra variables to the existing dict, e.g. via `c.Spawner.environment["myvar"] = "myvalue"`.
- `c.DockerSpawner.prefix` and `c.DockerSpawner.name_template` - if you change those, check whether your SSH environment variables permit those names a target. Also, think about setting `c.Authenticator.username_pattern` to prevent a user having a username that is also a valid container name.
- If you override ip and port connection settings, make sure to use Docker images that can handle those.

##### Kubernetes

To make modifications to the config in the Kubernetes setup, checkout the documentation for [Zero to JupyterHub with Kubernetes](https://zero-to-jupyterhub.readthedocs.io/en/latest/reference.html?highlight=service_account#singleuser). Our hub is compatible with their approach and so you can pass a config.yaml to the helm command to set values for the Jupyterhub config. We modified a few default values compared to the original repository.
[This file](https://github.com/ml-tooling/zero-to-mlhub-k8s/blob/master/jupyterhub/values.yaml) contains the default values for the helm deployment. The passed config is used by [the Jupyterhub config](https://github.com/ml-tooling/zero-to-mlhub-k8s/blob/master/images/hub/jupyterhub_config.py), which we load subsequently to the Jupyterhub config you find in this repo. Hence, the "Zero to JupyterHub with Kubernetes" config overrides the above described default config as it is loaded after our default config file. In short what happens: This repo's hub config is loaded, then the "Zero to JupyterHub with Kubernetes" config, where values can be modified via a config.yaml.

### Enable SSL/HTTPS

MLHub will automatically start with HTTPS. If you don't provide a certificate, it will generate one during startup. This is to make routing SSH connections possible as we use nginx to handle HTTPS & SSH on the same port.

<details>
<summary>Details (click to expand...)</summary>

If you have an own certificate, mount the certificate and key files as `cert.crt` and `cert.key`, respectively, as read-only at `/resources/ssl`, so that the container has access to `/resources/ssl/cert.crt` and `/resources/ssl/cert.key`.

</details>

### Spawner

We override [DockerSpawner](https://github.com/ml-tooling/ml-hub/blob/master/resources/mlhubspawner/mlhubspawner/mlhubspawner.py) and [KubeSpawner](https://github.com/ml-tooling/ml-hub/blob/master/resources/mlhubspawner/mlhubspawner/mlhubkubernetesspawner.py) for Docker and Kubernetes, respectively. We do so to add convenient labels and environment variables. Further, we return a custom option form to configure the resouces of the workspaces.

#### DockerSpawner

- We create a separate Docker network for each user, which means that (named) workspaces of the same user can see each other but workspaces of different users cannot see each other. Doing so adds another security layer in case a user starts a service within the own workspace and does not properly secure it.

#### KubeSpawner

- Create / delete services for a workspace, so that the hub can access them via Kubernetes DNS.

## Support

The ML Hub project is maintained by [@raethlein](https://twitter.com/raethlein) and [@LukasMasuch](https://twitter.com/LukasMasuch). Please understand that we won't be able
to provide individual support via email. We also believe that help is much more
valuable if it's shared publicly so that more people can benefit from it.

| Type                     | Channel                                              |
| ------------------------ | ------------------------------------------------------ |
| 🚨 **Bug Reports**       | <a href="https://github.com/ml-tooling/ml-hub/issues?utf8=%E2%9C%93&q=is%3Aopen+is%3Aissue+label%3Abug+sort%3Areactions-%2B1-desc+" title="Open Bug Report"><img src="https://img.shields.io/github/issues/ml-tooling/ml-hub/bug.svg"></a>                                 |
| 🎁 **Feature Requests**  | <a href="https://github.com/ml-tooling/ml-hub/issues?q=is%3Aopen+is%3Aissue+label%3Afeature-request+sort%3Areactions-%2B1-desc" title="Open Feature Request"><img src="https://img.shields.io/github/issues/ml-tooling/ml-hub/feature-request.svg?label=feature%20requests"></a>                                 |
| 👩‍💻 **Usage Questions**   |  <a href="https://stackoverflow.com/questions/tagged/ml-tooling" title="Open Question on Stackoverflow"><img src="https://img.shields.io/badge/stackoverflow-ml--tooling-orange.svg"></a> <a href="https://gitter.im/ml-tooling/ml-hub" title="Chat on Gitter"><img src="https://badges.gitter.im/ml-tooling/ml-hub.svg"></a> |
| 🗯 **General Discussion** | <a href="https://gitter.im/ml-tooling/ml-hub" title="Chat on Gitter"><img src="https://badges.gitter.im/ml-tooling/ml-hub.svg"></a>  <a href="https://twitter.com/mltooling" title="ML Tooling on Twitter"><img src="https://img.shields.io/twitter/follow/mltooling.svg?style=social"></a>

## Features

We have the three following scenarios in mind for the hub and want to point them out as a guideline. These three scenarios are thought of as an inspiration and are based on the default configuration by using [native-authenticator](https://github.com/ml-tooling/nativeauthenticator) as the hub authenticator. If you start the hub with a different authenticator or change other settings, you might want to or have to do things differently.

### Scenarios

#### Multi-user hub without self-service

In this scenario, the idea is that just the admin user exists and can access the hub. The admin user then creates workspaces and distributes them to users.

Go to the admin panel (1) and create a new user (2). 
You can then start the standard workspace for that user or create a new workspace (see second image).
Via the ssh access button (3), you can send the user a command to connect to the started workspace via ssh. For more information about the ssh-feature in the workspace, checkout [this documentation section](https://github.com/ml-tooling/ml-workspace#ssh-access). If you created a workspace for another user, it might be necessary to click access on the workspace and authorize once per user to be able to use the ssh-access button.

<img width=100% alt="Picture of admin panel" src="https://github.com/ml-tooling/ml-hub/raw/master/docs/images/admin-panel.png">
<img width=100% alt="Picture of admin panel" src="https://github.com/ml-tooling/ml-hub/raw/master/docs/images/create-workspace.png">

#### Multi-user hub with self-service

Give also non-admin users the permission to create named workspaces.

To give users access, the admin just has to authorize registered users.

<img width=100% alt="Picture of admin panel" src="https://github.com/ml-tooling/ml-hub/raw/master/docs/images/authorize-users.png">

#### User hub

Users can login and get a default workspace. No additional workspaces can be created.

To let users login and get a default workspace but not let them create new servers, just set the config option `c.JupyterHub.allow_named_servers` to `False` when starting the hub. Note that this also disables the ability for starting named servers for the admin. Currently, the workaround would be to have a second hub container just for the admin.

### Named Server Options Form

When named servers are allowed and the hub is started with the default config, you can create named servers. When doing so, you can set some configurations for the new workspace, such as resource limitations or mounting GPUs. Mounting GPUs is not possible in Kuberntes mode currently.
The "Days to live" flag is purely informational currently and can be seen in the admin view; it should help admins to keep an overview of workspaces.

<img width=100% alt="Picture of admin panel" src="https://github.com/ml-tooling/ml-hub/raw/master/docs/images/create-workspace-options.png">

## Contribution

- Pull requests are encouraged and always welcome. Read [`CONTRIBUTING.md`](https://github.com/ml-tooling/ml-hub/tree/master/CONTRIBUTING.md) and check out [help-wanted](https://github.com/ml-tooling/ml-hub/issues?utf8=%E2%9C%93&q=is%3Aopen+is%3Aissue+label%3A"help+wanted"+sort%3Areactions-%2B1-desc+) issues.
- Submit github issues for any [feature enhancements](https://github.com/ml-tooling/ml-hub/issues/new?assignees=&labels=feature-request&template=02_feature-request.md&title=), [bugs](https://github.com/ml-tooling/ml-hub/issues/new?assignees=&labels=bug&template=01_bug-report.md&title=), or [documentation](https://github.com/ml-tooling/ml-hub/issues/new?assignees=&labels=enhancement%2C+docs&template=03_documentation.md&title=) problems. 
- By participating in this project you agree to abide by its [Code of Conduct](https://github.com/ml-tooling/ml-hub/tree/master/CODE_OF_CONDUCT.md).

---

Licensed **Apache 2.0**. Created and maintained with ❤️ by developers from SAP in Berlin.
