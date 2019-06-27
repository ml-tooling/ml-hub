FROM jupyterhub/jupyterhub:1.0.0

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

RUN \
    mkdir /var/log/nginx && \
    mkdir /etc/nginx/nginx_plugins

RUN \
    pip install dockerspawner && \
    pip install git+https://github.com/jupyterhub/nativeauthenticator@919a37460cdb46ef536985c0cb0c1109d5e0e483 && \
    pip install git+https://github.com/ryanlovett/imagespawner

COPY docker-res/nginx.conf /etc/nginx/nginx.conf
COPY docker-res/lua-resty-http/ "/etc/nginx/nginx_plugins/lua-resty-http"

ENV \
    PATH=/usr/local/openresty/nginx/sbin:$PATH
