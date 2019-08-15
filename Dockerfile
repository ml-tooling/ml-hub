FROM mltooling/ssh-proxy:0.1.5

WORKDIR /

# Install Basics
RUN \
   apt-get update && \
   apt-get install -y build-essential libssl-dev zlib1g-dev && \
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
   apt-get install -y curl && \
   curl -sL https://deb.nodesource.com/setup_10.x | bash - && \
   apt-get install -y nodejs && \
   clean-layer.sh

# Install JupyterHub
RUN \
   npm install -g configurable-http-proxy && \
   python3 -m pip install --no-cache jupyterhub && \
   clean-layer.sh

# Install git as needed for installing pip repos from git
RUN \
   apt-get update && \
   apt-get install -y git && \
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
    touch $_RESOURCES_PATH/jupyterhub_user_config.py

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
   SSH_PERMIT_TARGET_PORT=8091 \
   SSH_PERMIT_TARGET_HOST="ws-*"

ENTRYPOINT /bin/bash $_RESOURCES_PATH/docker-entrypoint.sh
