FROM python:3-alpine

# ---- Build args for OCI labels ------------------------------------------------
ARG VERSION=1.0.2
ARG GIT_COMMIT=unknown
ARG BUILD_DATE=unknown

LABEL org.opencontainers.image.title="LFTP Mirror"
LABEL org.opencontainers.image.description="LFTP mirroring utility for synchronized directory transfers over SSH/FTP"
LABEL org.opencontainers.image.version="${VERSION}"
LABEL org.opencontainers.image.created="${BUILD_DATE}"
LABEL org.opencontainers.image.source="https://github.com/tyzen9/lftp-mirror"
LABEL org.opencontainers.image.revision="${GIT_COMMIT}"
LABEL org.opencontainers.image.authors="steve@tyzen9.com"
LABEL org.opencontainers.image.vendor="Tyzen9"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.url="https://github.com/tyzen9/lftp-mirror"
LABEL maintainer="steve@tyzen9.com"

# Install the Alpine libraries that we need using APK
RUN apk add --no-cache \
        bash \
        curl \
        lftp \
        openssh \
        gosu
        
# Set the working directory inside of the image's filesystem
WORKDIR /usr/src

# Install the required Python libraries
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Make a directory on the image's filesystem
# and copy the application into that directory
RUN mkdir -p tyzen9
COPY app/. tyzen9/.

# Make the /downloads directory to mount to
RUN mkdir /downloads

# Make a place to store the known hosts file
# RUN mkdir -p $HOME/.ssh && chmod 700 $HOME/.ssh

# Copy the lftp configuration file 
COPY lftp.conf /etc/.


# ---- Entrypoint --------------------------------------------------------------
COPY app/entrypoint.sh /usr/local/bin/lftp-mirror
RUN chmod +x /usr/local/bin/lftp-mirror
# --- NOTE: This is NOT executed when starting a dev container
ENTRYPOINT ["lftp-mirror"]
