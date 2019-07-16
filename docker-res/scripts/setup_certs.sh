SSLNAME=cert

[ -f /run/secrets/$SSLNAME.crt ] && cp /run/secrets/$SSLNAME.crt ${_SSL_RESOURCES_PATH}/$SSLNAME.crt > /dev/null
[ -f /run/secrets/$SSLNAME.key ] && cp /run/secrets/$SSLNAME.key ${_SSL_RESOURCES_PATH}/$SSLNAME.key > /dev/null
[ -f /run/secrets/$SSLNAME.pem ] && cp /run/secrets/$SSLNAME.pem ${_SSL_RESOURCES_PATH}/$SSLNAME.pem > /dev/null

if [ ! -f ${_SSL_RESOURCES_PATH}/$SSLNAME.crt ]; then
    SSLDAYS=365
    echo "Generate self-signed SSL certificate since no were provided during startup."
    openssl req -x509 -nodes -newkey rsa:2048 -keyout $SSLNAME.key -out $SSLNAME.crt  -days $SSLDAYS -subj '/C=DE/ST=Berlin/L=Berlin/CN=localhost' 2>/dev/null
    
    mv $SSLNAME.crt ${_SSL_RESOURCES_PATH}/$SSLNAME.crt > /dev/null 2>&1
    mv $SSLNAME.key ${_SSL_RESOURCES_PATH}/$SSLNAME.key > /dev/null 2>&1
fi

# trust certificate. used in case containers share the same certificate
cp ${_SSL_RESOURCES_PATH}/$SSLNAME.crt /usr/local/share/ca-certificates/
# update certificates, but dont print out information
update-ca-certificates > /dev/null
