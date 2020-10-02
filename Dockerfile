FROM mltooling/ssh-proxy:0.1.11

WORKDIR /

### INSTALL BASICS ###

# Set Debian Frontend to 'noninteractive' as needed for some programs/installations (e.g. sslh does not ask for mode during installation)
ENV \
   DEBIAN_FRONTEND="noninteractive" \
   _SSL_RESOURCES_PATH=$_RESOURCES_PATH/ssl

RUN \
   apt-get update && \
   apt-get install -y --no-install-recommends \
      build-essential libssl-dev zlib1g-dev \
      git \
      #python3 \
      python3-dev \
      #python3-pip \
      python3-setuptools \
      python3-wheel \
      libssl-dev \
      libcurl4-openssl-dev \
      build-essential \
      sqlite3 \
      curl \
      dnsutils \
      $(bash -c 'if [[ $JUPYTERHUB_VERSION == "git"* ]]; then \
        # workaround for https://bugs.launchpad.net/ubuntu/+source/nodejs/+bug/1794589
        echo nodejs=8.10.0~dfsg-2ubuntu0.2 nodejs-dev=8.10.0~dfsg-2ubuntu0.2 npm; \
      fi') \
      && \
   # Cleanup
   clean-layer.sh

# Add tini
RUN wget --quiet https://github.com/krallin/tini/releases/download/v0.18.0/tini -O /tini && \
    chmod +x /tini

# Install resty version of nginx
## We must build it ourselves as we need the newest version to tunnel SSH and HTTPS over the same port
RUN \
    apt-get update && \
    apt-get purge -y nginx nginx-common && \
    # libpcre required, otherwise you get a 'the HTTP rewrite module requires the PCRE library' error
    # Install apache2-utils to generate user:password file for nginx.
    apt-get install -y libssl-dev libpcre3 libpcre3-dev apache2-utils && \
    mkdir $_RESOURCES_PATH"/openresty" && \
    cd $_RESOURCES_PATH"/openresty" && \
    wget --quiet https://openresty.org/download/openresty-1.15.8.1.tar.gz  -O ./openresty.tar.gz && \
    tar xfz ./openresty.tar.gz && \
    rm ./openresty.tar.gz && \
    cd ./openresty-1.15.8.1/ && \
    # Surpress output - if there is a problem remove  > /dev/null
    ./configure --with-http_stub_status_module --with-http_sub_module > /dev/null && \
    make -j2 > /dev/null && \
    make install > /dev/null && \
    # create log dir and file - otherwise openresty will throw an error
    mkdir -p /var/log/nginx/ && \
    touch /var/log/nginx/upstream.log && \
    cd $_RESOURCES_PATH && \
    rm -r $_RESOURCES_PATH"/openresty" && \
    # Fix permissions
    chmod -R a+rwx $_RESOURCES_PATH && \
    # Cleanup
    clean-layer.sh

ENV \
   PATH=/usr/local/openresty/nginx/sbin:$PATH

# Install nodejs & npm for JupyterHub's configurable-http-proxy
RUN \
   apt-get update && \
   #apt-get install -y curl && \
   curl -sL https://deb.nodesource.com/setup_10.x | bash - && \
   apt-get install -y nodejs && \
   # Cleanup
   clean-layer.sh

# Install JupyterHub
RUN \
   npm install -g configurable-http-proxy && \
   python3 -m pip install --no-cache jupyterhub && \
   # Cleanup
   clean-layer.sh

### END BASICS ###

### MLHUB-SPECIFIC INSTALLATIONS ###

# Copy mlhubspawner module to install it
COPY resources/mlhubspawner /mlhubspawner

RUN \
   pip install --no-cache git+https://github.com/jupyterhub/dockerspawner@d1f27e2855d2cefbdb25b29cc069b9ca69d564e3 && \
   pip install --no-cache git+https://github.com/ml-tooling/nativeauthenticator@9859a69dcc9d2ae8d827f192a1580d86f897e9f1 && \
   pip install --no-cache git+https://github.com/jupyterhub/ldapauthenticator@b32a5ea23449edc0519ba4cd86dd0cc0c36896d5 && \
   pip install --no-cache git+https://github.com/ryanlovett/imagespawner && \
   pip install --no-cache /mlhubspawner && \
   rm -r /mlhubspawner && \
   pip install tornado==5.1.1 && \
   # Cleanup
   clean-layer.sh

### END MLHUB-SPECIFIC INSTALLATIONS ###

### INCUBATION ZONE ###

# Kubernetes Support
ADD https://raw.githubusercontent.com/ml-tooling/zero-to-mlhub-k8s/master/images/hub/cull_idle_servers.py /usr/local/bin/cull_idle_servers.py
ADD resources/kubernetes/jupyterhub_chart_config.py $_RESOURCES_PATH/jupyterhub_chart_config.py
# Copy the jupyterhub config that has a lot of options to be configured

RUN chmod u+rx /usr/local/bin/cull_idle_servers.py 

RUN pip3 install oauthenticator psutil yamlreader pyjwt \
         # https://github.com/jupyterhub/kubespawner
         # https://pypi.org/project/jupyterhub-kubespawner
         jupyterhub-kubespawner==0.11.* \
         # https://github.com/kubernetes-client/python
         # https://pypi.org/project/kubernetes
         kubernetes==10.0.* \
         # https://pypi.org/project/pycurl/
         pycurl==7.43.0.*
RUN apt-get update && apt-get install -y pcregrep && clean-layer.sh

### END INCUBATION ZONE ###

### CONFIGURATION ###

ARG ARG_HUB_VERSION="unknown"
ENV HUB_VERSION=$ARG_HUB_VERSION

COPY resources/nginx.conf /etc/nginx/nginx.conf
COPY resources/scripts $_RESOURCES_PATH/scripts
COPY resources/docker-entrypoint.sh $_RESOURCES_PATH/docker-entrypoint.sh
COPY resources/logo.png /usr/local/share/jupyterhub/static/images/jupyter.png
COPY resources/jupyterhub_config.py $_RESOURCES_PATH/jupyterhub_config.py
COPY resources/jupyterhub-mod/template-home.html /usr/local/share/jupyterhub/templates/home.html
COPY resources/jupyterhub-mod/template-admin.html /usr/local/share/jupyterhub/templates/admin.html
COPY resources/jupyterhub-mod/ssh-dialog-snippet.html /usr/local/share/jupyterhub/templates/ssh-dialog-snippet.html
COPY resources/jupyterhub-mod/info-dialog-snippet.html /usr/local/share/jupyterhub/templates/info-dialog-snippet.html
COPY resources/jupyterhub-mod/version-number-snippet.html /usr/local/share/jupyterhub/templates/version-number-snippet.html
COPY resources/jupyterhub-mod/jsonpresenter /usr/local/share/jupyterhub/static/components/jsonpresenter/
COPY resources/jupyterhub-mod/cleanup-service.py /resources/cleanup-service.py

RUN \
   touch $_RESOURCES_PATH/jupyterhub_user_config.py && \
   mkdir $_SSL_RESOURCES_PATH && chmod ug+rwx $_SSL_RESOURCES_PATH && \
   chmod -R ug+rxw $_RESOURCES_PATH/scripts && \
   chmod ug+rwx $_RESOURCES_PATH/docker-entrypoint.sh

RUN \
   # Replace the variable with the actual value. There seems to be no direct functionality in ninja-templates
   sed -i "s/\$HUB_VERSION/$HUB_VERSION/g" /usr/local/share/jupyterhub/templates/version-number-snippet.html

# Set python3 to default python. Needed for the ssh-proxy scripts
RUN \
   rm /usr/bin/python && \
   ln -s /usr/bin/python3 /usr/bin/python

ENV \
   DEFAULT_WORKSPACE_PORT=8080 \
   SSH_PERMIT_TARGET_PORT=8080 \
   SSH_PERMIT_TARGET_HOST="ws-*" \
   START_NGINX=true \
   START_SSH=true \
   START_JHUB=true \
   START_CHP=false \
   EXECUTION_MODE="local" \
   HUB_NAME="mlhub" \ 
   CLEANUP_INTERVAL_SECONDS=3600 \
   DYNAMIC_WHITELIST_ENABLED="false" \
   IS_CLEANUP_SERVICE_ENABLED="true"

### END CONFIGURATION ###

### LABELS ###

ARG ARG_BUILD_DATE="unknown"
ARG ARG_VCS_REF="unknown"

# Overwrite & add common labels
LABEL \
    "maintainer"="mltooling.team@gmail.com" \
    # Kubernetes Labels
    "io.k8s.description"="Multi-user hub which spawns and manages workspace instances." \
    "io.k8s.display-name"="Machine Learning Hub" \
    # Openshift labels: https://docs.okd.io/latest/creating_images/metadata.html
    "io.openshift.expose-services"="8080:http, 5901:xvnc" \
    "io.openshift.non-scalable"="true" \
    "io.openshift.tags"="workspace, machine learning, vnc, ubuntu, xfce" \
    "io.openshift.min-memory"="1Gi" \
    # Open Container labels: https://github.com/opencontainers/image-spec/blob/master/annotations.md
    "org.opencontainers.image.title"="Machine Learning Hub" \
    "org.opencontainers.image.description"="Multi-user hub which spawns and manages workspace instances." \
    "org.opencontainers.image.documentation"="https://github.com/ml-tooling/ml-hub" \
    "org.opencontainers.image.url"="https://github.com/ml-tooling/ml-hub" \
    "org.opencontainers.image.source"="https://github.com/ml-tooling/ml-hub" \
    "org.opencontainers.image.licenses"="Apache-2.0" \
    "org.opencontainers.image.version"=$HUB_VERSION \
    "org.opencontainers.image.vendor"="ML Tooling" \
    "org.opencontainers.image.authors"="Benjamin Raehtlein & Lukas Masuch" \
    "org.opencontainers.image.revision"=$ARG_VCS_REF \
    "org.opencontainers.image.created"=$ARG_BUILD_DATE \ 
    # Label Schema Convention (deprecated): http://label-schema.org/rc1/
    "org.label-schema.name"="Machine Learning Hub" \
    "org.label-schema.description"="Multi-user hub which spawns and manages workspace instances." \
    "org.label-schema.usage"="https://github.com/ml-tooling/ml-hub" \
    "org.label-schema.url"="https://github.com/ml-tooling/ml-hub" \
    "org.label-schema.vcs-url"="https://github.com/ml-tooling/ml-hub" \
    "org.label-schema.vendor"="ML Tooling" \
    "org.label-schema.version"=$HUB_VERSION \
    "org.label-schema.schema-version"="1.0" \
    "org.label-schema.vcs-ref"=$ARG_VCS_REF \
    "org.label-schema.build-date"=$ARG_BUILD_DATE
    
### END LABELS ###

# use global option with tini to kill full process groups: https://github.com/krallin/tini#process-group-killing
ENTRYPOINT ["/tini", "-g", "--"]

# Entrypoint must use the array notation, otherwise the entrypoint.sh script does not receive passed cmd arguments (probably because Docker will start it like this: /bin/sh -c /bin/bash /resources/docker-entrypoint.sh <cmd-args>)
CMD ["/bin/bash", "/resources/docker-entrypoint.sh"]

# The port on which nginx listens and checks whether it's http(s) or ssh traffic
EXPOSE 8080
 
