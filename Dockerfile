#FROM jupyterhub/jupyterhub:1.0.0
FROM mltooling/ssh-proxy:0.1.2

WORKDIR /

RUN \
    apt-get update && \
    apt-get install -y build-essential libssl-dev zlib1g-dev

# Install resty version of nginx
## We must build it ourselves as we need the newest version to tunnel SSH and HTTPS over the same port
RUN \
    # apt-get purge -y nginx nginx-common && \
    # wget -qO - https://openresty.org/package/pubkey.gpg | sudo apt-key add - && \
    # apt-get -y install software-properties-common && \
    # add-apt-repository -y "deb http://openresty.org/package/ubuntu $(lsb_release -sc) main" && \
    apt-get update && \
    # apt-get install -y openresty
    apt-get purge -y nginx nginx-common && \
    apt-get update && \
    apt-get install -y libssl-dev && \
    # libpcre required, otherwise you get a 'the HTTP rewrite module requires the PCRE library' error
    apt-get install -y libpcre3 libpcre3-dev && \
    wget https://openresty.org/download/openresty-1.15.8.1rc1.tar.gz && \
    tar -xvf openresty-1.15.8.1rc1.tar.gz 
    #&& \
    #cd /openresty-1.15.8.1rc1/configure && \
   # ./configure -j2
RUN \
    apt-get install -y build-essential && \
    cd /openresty-1.15.8.1rc1/ && \
    ./configure --with-http_stub_status_module --with-http_sub_module && \
    make -j2 && \
    make install && \
    apt-get clean

# Install nodejs & npm for JupyterHub's configurable-http-proxy
RUN \
   apt-get install -y curl && \
   curl -sL https://deb.nodesource.com/setup_10.x | bash - && \
   apt-get install -y nodejs

# Install JupyterHub
RUN \
   npm install -g configurable-http-proxy && \
   python3 -m pip install jupyterhub   

# Install git as needed for installing pip repos from git
RUN \
   apt-get install -y git

RUN \
    pip install dockerspawner && \
    pip install git+https://github.com/jupyterhub/nativeauthenticator@919a37460cdb46ef536985c0cb0c1109d5e0e483 && \
    pip install git+https://github.com/ryanlovett/imagespawner

COPY docker-res/nginx.conf /etc/nginx/nginx.conf
COPY docker-res/lua-resty-http/ "/etc/nginx/nginx_plugins/lua-resty-http"
COPY docker-res/scripts $_RESOURCES_PATH/scripts
COPY docker-res/docker-entrypoint.sh $_RESOURCES_PATH/docker-entrypoint.sh
COPY docker-res/mlhubspawner /mlhubspawner
COPY docker-res/jupyterhub_config.py $_RESOURCES_PATH/jupyterhub_config.py
COPY docker-res/jupyterhub-mod/template-page.html /usr/local/share/jupyterhub/templates/page.html
COPY docker-res/jupyterhub-mod/template-home.html /usr/local/share/jupyterhub/templates/home.html

RUN \
    mkdir /var/log/nginx && \
    touch $_RESOURCES_PATH/jupyterhub_user_config.py

RUN \
   pip install /mlhubspawner && \
   rm -r /mlhubspawner

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

ENV SSH_PERMIT_TARGET_PORT=8091

ENTRYPOINT /bin/bash $_RESOURCES_PATH/docker-entrypoint.sh
