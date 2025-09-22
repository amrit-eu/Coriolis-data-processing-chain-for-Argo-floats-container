FROM gitlab-registry.ifremer.fr/ifremer-commons/docker/images/ubuntu:22.04 AS development

RUN \
    apt-get -y update && \
    apt-get -y install wget unzip && \
    apt-get clean && \
    mkdir -p /tmp/config

WORKDIR /tmp

COPY decArgo_soft/exec/run_decode_argo_2_nc_rt.sh .
COPY decArgo_soft/exec/decode_argo_2_nc_rt .
COPY decArgo_soft/config/configuration_sample_files_docker/*.json ./config
COPY decArgo_soft/config/_configParamNames ./config/_configParamNames
COPY decArgo_soft/config/_techParamNames ./config/_techParamNames


FROM gitlab-registry.ifremer.fr/ifremer-commons/docker/images/ubuntu:22.04 AS runtime

# configurable arguments
ARG RUN_FILE=run_decode_argo_2_nc_rt.sh
ARG GROUPID=9999
ARG DATA_DIR=/mnt/data
ARG RUNTIME_DIR=/mnt/runtime
ARG REF_DIR=/mnt/ref
ENV APP_DIR=/app

# environment variables
ENV DATA_HOME=${DATA_DIR} \
    RUNTIME_HOME=${RUNTIME_DIR} \
    REF_HOME=${REF_DIR} \
    APP_HOME=${APP_DIR} \
    APP_RUN_FILE=${RUN_FILE} \
    MCR_CACHE_ROOT=/tmp/matlab-cache \
    LD_LIBRARY_PATH=/mnt/runtime/runtime/glnxa64:/mnt/runtime/bin/glnxa64:/mnt/runtime/sys/os/glnxa64:/mnt/runtime/sys/opengl/lib/glnxa64

# prepare os environment
RUN \
    apt-get -y update && \
    apt-get -y upgrade && \
    apt-get -y install wget libxtst6 libxt6 && \
    groupadd --gid ${GROUPID} gbatch && \
    apt-get purge -y manpages manpages-dev && \
    apt-get autoremove -y && \
    apt-get autoclean -y && \
    apt-get clean -y && \
    rm -rf /usr/share/locale/* /var/cache/debconf/* /var/lib/apt/lists/* /usr/share/doc/*

WORKDIR ${APP_DIR}

COPY --from=development /tmp/ .

RUN chown -R root:gbatch ${APP_DIR} /mnt && chmod -R 770 ${APP_DIR} /mnt

CMD ["tail", "-f", "/dev/null"]
