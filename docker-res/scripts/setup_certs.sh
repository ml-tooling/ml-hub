SSLNAME=cert

cp /run/secrets/$SSLNAME.crt ${SSL_RESOURCES_PATH}/$SSLNAME.crt
cp /run/secrets/$SSLNAME.key ${SSL_RESOURCES_PATH}/$SSLNAME.key
cp /run/secrets/$SSLNAME.pem ${SSL_RESOURCES_PATH}/$SSLNAME.pem

if [ ! -f ${_SSL_RESOURCES_PATH}/$SSLNAME.crt ]; then
    SSLDAYS=365

    openssl req -x509 -nodes -newkey rsa:2048 \
        -keyout $SSLNAME.key \
        -out $SSLNAME.crt \
        -days $SSLDAYS \
        -subj '/C=DE/ST=Berlin/L=Berlin/CN=localhost'

    mv $SSLNAME.crt ${_SSL_RESOURCES_PATH}/$SSLNAME.crt
    mv $SSLNAME.key ${_SSL_RESOURCES_PATH}/$SSLNAME.key
fi

# trust certificate. used in case containers share the same certificate
cp ${_SSL_RESOURCES_PATH}/$SSLNAME.crt /usr/local/share/ca-certificates/
update-ca-certificates
