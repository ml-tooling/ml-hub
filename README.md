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

- 💫 Create, manage, and access Jupyter notebooks.
- 🖊️ Set configuration parameters such as CPU-limits for started workspaces. 
- 🖥 Access additional tools within the started workspaces by having secured routes.
- 🎛 Tunnel SSH connections to workspace containers.

## Getting Started

### Prerequisites

- Docker

Most parts will be identical to the configuration of Jupyterhub 1.0.0. One of the things that are different is that ssl will not be activated on proxy or hub-level, but on our nginx proxy.

### Start an instance via Docker

```bash
docker run \
    -p 8091 \
    --name mlhub \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v jupyterhub_data:/data \
    ml-hub:latest
```

To persist the hub data, such as started workspaces and created users, mount a directory to `/data` (`-v`).

For Kubernetes deployment, we forked and modified [zero-to-jupyterhub-k8s](https://github.com/jupyterhub/zero-to-jupyterhub-k8s) which you can find [here](https://github.com/ml-tooling/zero-to-mlhub-k8s).

### Configuration

MLHub is based on [SSH Proxy](https://github.com/ml-tooling/ssh-proxy). Check out SSH Proxy for ssh-related configurations.

<table>
    <tr>
        <th>Variable</th>
        <th>Description</th>
        <th>Default</th>
    </tr>
    <tr>
        <td>START_SSH</td>
        <td>Start the sshd process which is used to tunnel ssh to the workspaces.</td>
        <td>true</td>
    </tr>
    <tr>
        <td>START_NGINX</td>
        <td>Whether or not to start the nginx proxy. If the Hub should be used without additional tool routing to workspaces, this could be disabled. SSH port 22 would need to be published separately then. This option is built-in to work with [zero-to-mlhub-k8s](https://github.com/ml-tooling/zero-to-mlhub-k8s)</td>
        <td>true</td>
    </tr>
    <tr>
        <td>START_JHUB</td>
        <td>Start the Jupyterhub hub. This option is built-in to work with [zero-to-mlhub-k8s](https://github.com/ml-tooling/zero-to-mlhub-k8s), where the image is also used as the CHP image.</td>
        <td>true</td>
    </tr>
    <tr>
        <td>START_CHP</td>
        <td>Start the Jupyterhub proxy process separately (The hub should not start the proxy itself, which can be configured via the Jupyterhub config file. This option is built-in to work with [zero-to-mlhub-k8s](https://github.com/ml-tooling/zero-to-mlhub-k8s), where the image is also used as the CHP image.</td>
        <td>false</td>
    </tr>

</table>

### Enable SSL/HTTPS

MLHub will automatically start with HTTPS. If you don't provide a certificate, it will generate one on startup. This is to make routing SSH connections possible as we use nginx to handle HTTPS & SSH on the same port.

<details>
<summary>Details (click to expand...)</summary>

If you have an own certificate, mount the certificate and key files as `cert.crt` and `cert.key`, respectively, as read-only at `/resources/ssl`, so that the container has access to `/resources/ssl/cert.crt` and `/resources/ssl/cert.key`.

</details>

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

_WIP: Describe features with screenshots_

## Contribution

- Pull requests are encouraged and always welcome. Read [`CONTRIBUTING.md`](https://github.com/ml-tooling/ml-hub/tree/master/CONTRIBUTING.md) and check out [help-wanted](https://github.com/ml-tooling/ml-hub/issues?utf8=%E2%9C%93&q=is%3Aopen+is%3Aissue+label%3A"help+wanted"+sort%3Areactions-%2B1-desc+) issues.
- Submit github issues for any [feature enhancements](https://github.com/ml-tooling/ml-hub/issues/new?assignees=&labels=feature-request&template=02_feature-request.md&title=), [bugs](https://github.com/ml-tooling/ml-hub/issues/new?assignees=&labels=bug&template=01_bug-report.md&title=), or [documentation](https://github.com/ml-tooling/ml-hub/issues/new?assignees=&labels=enhancement%2C+docs&template=03_documentation.md&title=) problems. 
- By participating in this project you agree to abide by its [Code of Conduct](https://github.com/ml-tooling/ml-hub/tree/master/CODE_OF_CONDUCT.md).

---

Licensed **Apache 2.0**. Created and maintained with ❤️ by developers from SAP in Berlin.