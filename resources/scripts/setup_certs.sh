SSLNAME=cert

[ -f /run/secrets/$SSLNAME.crt ] && cp /run/secrets/$SSLNAME.crt ${_SSL_RESOURCES_PATH}/$SSLNAME.crt
[ -f /run/secrets/$SSLNAME.key ] && cp /run/secrets/$SSLNAME.key ${_SSL_RESOURCES_PATH}/$SSLNAME.key
[ -f /run/secrets/$SSLNAME.pem ] && cp /run/secrets/$SSLNAME.pem ${_SSL_RESOURCES_PATH}/$SSLNAME.pem

if [ ! -f ${_SSL_RESOURCES_PATH}/$SSLNAME.crt ]; then
    echo "No certificate was provided for SSL/HTTPS."
    echo "Generate self-signed certificate for SSL/HTTPS."

    SSLDAYS=365
    touch /root/.rnd
    openssl req -x509 -nodes -newkey rsa:2048 -keyout $SSLNAME.key -out $SSLNAME.crt  -days $SSLDAYS -subj '/C=DE/ST=Berlin/L=Berlin/CN=localhost' -reqexts SAN -extensions SAN -config <(cat /etc/ssl/openssl.cnf <(printf "\n[SAN]\nsubjectAltName=DNS:localhost,DNS:127.0.0.1\n")) > /dev/null 2>&1
    
    mv $SSLNAME.crt ${_SSL_RESOURCES_PATH}/$SSLNAME.crt
    mv $SSLNAME.key ${_SSL_RESOURCES_PATH}/$SSLNAME.key
else
    echo "Certificate for SSL/HTTPS was found in "${_SSL_RESOURCES_PATH}
fi

# trust certificate. used in case containers share the same certificate
cp ${_SSL_RESOURCES_PATH}/$SSLNAME.crt /usr/local/share/ca-certificates/
# update certificates, but dont print out information
update-ca-certificates > /dev/null
