FROM buildpack-deps:bionic

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Set up locales properly
RUN apt-get -qq update && \
    apt-get -qq install --yes --no-install-recommends locales > /dev/null && \
    apt-get -qq purge && \
    apt-get -qq clean && \
    rm -rf /var/lib/apt/lists/*

RUN echo "en_US.UTF-8 UTF-8" > /etc/locale.gen && \
    locale-gen

ENV LC_ALL en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US.UTF-8

# Use bash as default shell, rather than sh
ENV SHELL /bin/bash

# Set up user
ARG NB_USER
ARG NB_UID
ENV USER ${NB_USER}
ENV HOME /home/${NB_USER}

RUN groupadd \
        --gid ${NB_UID} \
        ${NB_USER} && \
    useradd \
        --comment "Default user" \
        --create-home \
        --gid ${NB_UID} \
        --no-log-init \
        --shell /bin/bash \
        --uid ${NB_UID} \
        ${NB_USER}

# Base package installs are not super interesting to users, so hide their outputs
# If install fails for some reason, errors will still be printed
RUN apt-get -qq update && \
    apt-get -qq install --yes --no-install-recommends \
       less \
       unzip \
       > /dev/null && \
    apt-get -qq purge && \
    apt-get -qq clean && \
    rm -rf /var/lib/apt/lists/*

EXPOSE 8888

# Environment variables required for build
ENV APP_BASE /srv
ENV CONDA_DIR ${APP_BASE}/conda
ENV NB_PYTHON_PREFIX ${CONDA_DIR}/envs/notebook
ENV NPM_DIR ${APP_BASE}/npm
ENV NPM_CONFIG_GLOBALCONFIG ${NPM_DIR}/npmrc
ENV NB_ENVIRONMENT_FILE /tmp/env/environment.lock
ENV MAMBA_ROOT_PREFIX ${CONDA_DIR}
ENV MAMBA_EXE ${CONDA_DIR}/bin/mamba
ENV KERNEL_PYTHON_PREFIX ${NB_PYTHON_PREFIX}
# Special case PATH
ENV PATH ${NB_PYTHON_PREFIX}/bin:${CONDA_DIR}/bin:${NPM_DIR}/bin:${PATH}
# If scripts required during build are present, copy them

COPY --chown=1000:1000 build_script_files/-2fusers-2fdecitre-2fvirtualenv-2fsearch-5fnotebook3-2flib-2fpython3-2e9-2fsite-2dpackages-2frepo2docker-2fbuildpacks-2fconda-2factivate-2dconda-2esh-975c3c /etc/profile.d/activate-conda.sh

COPY --chown=1000:1000 build_script_files/-2fusers-2fdecitre-2fvirtualenv-2fsearch-5fnotebook3-2flib-2fpython3-2e9-2fsite-2dpackages-2frepo2docker-2fbuildpacks-2fconda-2fenvironment-2epy-2d3-2e9-2elock-ca8819 /tmp/env/environment.lock

COPY --chown=1000:1000 build_script_files/-2fusers-2fdecitre-2fvirtualenv-2fsearch-5fnotebook3-2flib-2fpython3-2e9-2fsite-2dpackages-2frepo2docker-2fbuildpacks-2fconda-2finstall-2dbase-2denv-2ebash-811eef /tmp/install-base-env.bash
RUN TIMEFORMAT='time: %3R' \
bash -c 'time /tmp/install-base-env.bash' && \
rm -rf /tmp/install-base-env.bash /tmp/env

RUN mkdir -p ${NPM_DIR} && \
chown -R ${NB_USER}:${NB_USER} ${NPM_DIR}


# ensure root user after build scripts
USER root

# Allow target path repo is cloned to be configurable
ARG REPO_DIR=${HOME}
ENV REPO_DIR ${REPO_DIR}
WORKDIR ${REPO_DIR}
RUN chown ${NB_USER}:${NB_USER} ${REPO_DIR}

# We want to allow two things:
#   1. If there's a .local/bin directory in the repo, things there
#      should automatically be in path
#   2. postBuild and users should be able to install things into ~/.local/bin
#      and have them be automatically in path
#
# The XDG standard suggests ~/.local/bin as the path for local user-specific
# installs. See https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html
ENV PATH ${HOME}/.local/bin:${REPO_DIR}/.local/bin:${PATH}

# The rest of the environment
ENV CONDA_DEFAULT_ENV ${KERNEL_PYTHON_PREFIX}
# Run pre-assemble scripts! These are instructions that depend on the content
# of the repository but don't access any files in the repository. By executing
# them before copying the repository itself we can cache these steps. For
# example installing APT packages.

# ensure root user after preassemble scripts
USER root

# Copy stuff.
COPY --chown=1000:1000 src/ ${REPO_DIR}

# Run assemble scripts! These will actually turn the specification
# in the repository into an image.


# Container image Labels!
# Put these at the end, since we don't want to rebuild everything
# when these change! Did I mention I hate Dockerfile cache semantics?

LABEL repo2docker.ref="None"
LABEL repo2docker.repo="local"
LABEL repo2docker.version="2022.02.0"

# We always want containers to run as non-root
USER ${NB_USER}

# Make sure that postBuild scripts are marked executable before executing them
RUN chmod +x .binder/postBuild
RUN ./.binder/postBuild

# Add start script
# Add entrypoint
ENV PYTHONUNBUFFERED=1
COPY /python3-login /usr/local/bin/python3-login
COPY /repo2docker-entrypoint /usr/local/bin/repo2docker-entrypoint
ENTRYPOINT ["/usr/local/bin/repo2docker-entrypoint"]

# Specify the default command to run
CMD ["jupyter", "notebook", "--ip", "0.0.0.0"]