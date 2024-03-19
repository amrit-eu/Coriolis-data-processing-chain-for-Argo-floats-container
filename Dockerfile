FROM gitlab-registry.ifremer.fr/ifremer-commons/docker/images/ubuntu:22.04 as prepare

RUN \
    apt-get -y update && \
    apt-get -y install wget unzip

ARG HEADER_TOKEN
ARG APP_VERSION
ARG APP_FILENAME

WORKDIR /tmp

RUN \
    wget --header "${HEADER_TOKEN}" https://gitlab.ifremer.fr/api/v4/projects/4282/packages/generic/decode_argo/${APP_VERSION}/${APP_FILENAME} && \
    unzip ${APP_FILENAME} && \
    rm ${APP_FILENAME}

FROM gitlab-registry.ifremer.fr/ifremer-commons/docker/images/ubuntu:22.04 as runtime-base

# confifurable arguments
ARG RUN_FILE=run_decode_argo_2_nc_rt.sh
ARG GROUPID=9999
ARG DATA_DIR=/mnt/data
ARG RUNTIME_DIR=/mnt/runtime
ARG REF_DIR=/mnt/ref
ENV APP_DIR=/app

# environment variables
ENV DATA_HOME=${DATA_DIR}
ENV RUNTIME_HOME=${RUNTIME_DIR}
ENV REF_HOME=${REF_DIR}
ENV APP_HOME=${APP_DIR}
ENV APP_RUN_FILE=${RUN_FILE}
ENV MCR_CACHE_ROOT=/tmp/matlab/cache

# prepare os environment
RUN \
    apt-get -y update && \
    echo "===== MISE A JOUR OS =====" && \
    apt-get -y upgrade && \
    echo "===== ADD TOOLS LIBRARIES =====" && \
    apt-get -y install wget && \
    echo "===== ADD MATLAB REQUIRED LIBRARIES =====" && \
    apt-get -y install libxtst6 libxt6 && \
    echo "===== CREATION GROUPE UNIX gbatch (gid = ${GROUPID}) =====" && \
    groupadd --gid ${GROUPID} gbatch && \
    echo "===== GENERAL SYSTEM CLEANUP =====" && \
    apt-get purge -y manpages manpages-dev && \
    apt-get autoremove -y && \
    apt-get autoclean -y && \
    apt-get clean -y && \
    rm -rf /usr/share/locale/* && \
    rm -rf /var/cache/debconf/* && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /usr/share/doc/*

WORKDIR ${APP_DIR}

COPY --from=prepare /tmp/ .
COPY entrypoint.sh .

# adjust rights
RUN \
    chown -R root:gbatch ${APP_DIR} /mnt /tmp && \
    chmod -R 770 ${APP_DIR} /mnt /tmp

# classique runtime image
FROM runtime-base as runtime

ENTRYPOINT ["/app/entrypoint.sh"]

# Galaxy runtime image
FROM runtime-base as runtime-galaxy

RUN \
    apt-get -y update && \
    echo "===== ADD TOOLS LIBRARIES =====" && \
    apt-get -y install zip unzip

COPY --chown=root:gbatch ./R2022b /mnt/runtime

USER 1000:${GROUPID}