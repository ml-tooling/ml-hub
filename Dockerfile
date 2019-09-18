FROM mltooling/ssh-proxy:0.1.8

WORKDIR /

# Install Basics
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
   clean-layer.sh

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

# Install nodejs & npm for JupyterHub's configurable-http-proxy
RUN \
   apt-get update && \
   #apt-get install -y curl && \
   curl -sL https://deb.nodesource.com/setup_10.x | bash - && \
   apt-get install -y nodejs && \
   clean-layer.sh

# Install JupyterHub
RUN \
   npm install -g configurable-http-proxy && \
   python3 -m pip install --no-cache jupyterhub && \
   clean-layer.sh

# Install git as needed for installing pip repos from git
# RUN \
#    apt-get update && \
#    apt-get install -y git && \
#    clean-layer.sh

# Set Debian Frontend to 'noninteractive' so that sslh does not ask for mode during installation
ENV \
  DEBIAN_FRONTEND="noninteractive"
RUN \
   apt-get update && \
   apt-get install -y --no-install-recommends sslh && \
   clean-layer.sh

RUN \
   pip install --no-cache dockerspawner && \
   pip install --no-cache git+https://github.com/ml-tooling/nativeauthenticator@8ba7a1a4757101c723e59e78d928c2264ec3c973 && \
   pip install --no-cache git+https://github.com/ryanlovett/imagespawner && \
   clean-layer.sh

COPY docker-res/nginx.conf /etc/nginx/nginx.conf
COPY docker-res/scripts $_RESOURCES_PATH/scripts
COPY docker-res/docker-entrypoint.sh $_RESOURCES_PATH/docker-entrypoint.sh
COPY docker-res/mlhubspawner /mlhubspawner
COPY docker-res/logo.png /usr/local/share/jupyterhub/static/images/jupyter.png
COPY docker-res/jupyterhub_config.py $_RESOURCES_PATH/jupyterhub_config.py
COPY docker-res/jupyterhub-mod/template-home.html /usr/local/share/jupyterhub/templates/home.html
COPY docker-res/jupyterhub-mod/template-admin.html /usr/local/share/jupyterhub/templates/admin.html

RUN \
    touch $_RESOURCES_PATH/jupyterhub_user_config.py && \
    # just temp until helm chart is updated
    cp $_RESOURCES_PATH/jupyterhub_config.py /srv/jupyterhub_config.py

RUN \
   pip install --no-cache /mlhubspawner && \
   rm -r /mlhubspawner && \
   pip install tornado==5.1.1 && \
   clean-layer.sh

ENV \
   _SSL_RESOURCES_PATH=$_RESOURCES_PATH/ssl \
   PATH=/usr/local/openresty/nginx/sbin:$PATH

RUN \
  mkdir $_SSL_RESOURCES_PATH && chmod ug+rwx $_SSL_RESOURCES_PATH && \
  chmod -R ug+rxw $_RESOURCES_PATH/scripts && \
  chmod ug+rwx $_RESOURCES_PATH/docker-entrypoint.sh

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
   EXECUTION_MODE="local"

# Entrypoint must use the array notation, otherwise the entrypoint.sh script does not receive passed cmd arguments (probably because Docker will start it like this: /bin/sh -c /bin/bash /resources/docker-entrypoint.sh <cmd-args>)
ENTRYPOINT ["/bin/bash", "/resources/docker-entrypoint.sh"]

# Kubernetes Support
ADD https://raw.githubusercontent.com/ml-tooling/zero-to-mlhub-k8s/master/images/hub/z2jh.py /usr/local/lib/python3.6/dist-packages/z2jh.py
ADD https://raw.githubusercontent.com/ml-tooling/zero-to-mlhub-k8s/master/images/hub/cull_idle_servers.py /usr/local/bin/cull_idle_servers.py
# Copy the jupyterhub config that has a lot of options to be configured
ADD https://raw.githubusercontent.com/ml-tooling/zero-to-mlhub-k8s/master/images/hub/jupyterhub_config.py $_RESOURCES_PATH/kubernetes/jupyterhub_chart_config.py
ADD https://raw.githubusercontent.com/ml-tooling/zero-to-mlhub-k8s/master/images/hub/requirements.txt /tmp/requirements.txt

RUN PYCURL_SSL_LIBRARY=openssl pip3 install --no-cache-dir \
         -r /tmp/requirements.txt && \
         chmod u+rx /usr/local/bin/cull_idle_servers.py && \
         chmod u+rx /usr/local/lib/python3.6/dist-packages/z2jh.py
