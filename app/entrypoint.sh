#!/bin/sh
set -e

# Set the PUID and GIUD from the enviroment, or default to 1000:1000
PUID=${PUID:-1000}
PGID=${PGID:-1000}

# Setup the local group to run as
GROUPNAME="appgroup"
if getent group "$GROUPNAME" >/dev/null; then
    EXISTING_GID=$(getent group "$GROUPNAME" | cut -d: -f3)
    if [ "$EXISTING_GID" != "$PGID" ]; then
        delgroup "$GROUPNAME" || true
    fi
fi
if ! getent group "$GROUPNAME" >/dev/null; then
    addgroup -g "$PGID" "$GROUPNAME"
fi

# Setup the local user to run as
USERNAME="appuser"
if getent passwd "$USERNAME" >/dev/null; then
    EXISTING_UID=$(getent passwd "$USERNAME" | cut -d: -f3)
    if [ "$EXISTING_UID" != "$PUID" ]; then
        deluser "$USERNAME" || true
        delgroup "$GROUPNAME" 2>/dev/null || true
        addgroup -g "$PGID" "$GROUPNAME"
    fi
fi
if ! getent passwd "$USERNAME" >/dev/null; then
    adduser -D -u "$PUID" -G "$GROUPNAME" -s /bin/sh "$USERNAME"
fi

# Create the local user home directory
USER_HOME="/home/appuser"
mkdir -p "$USER_HOME"
chown "$PUID:$PGID" "$USER_HOME"

# Create a place to hold .ssh keys. This is critical to LFTP functionality
SSH_DIR="$USER_HOME/.ssh"
mkdir -p "$SSH_DIR"
chmod 700 "$SSH_DIR"
chown "$PUID:$PGID" "$SSH_DIR"
touch "$SSH_DIR/known_hosts"
chmod 600 "$SSH_DIR/known_hosts"
chown "$PUID:$PGID" "$SSH_DIR/known_hosts"

# Output some initialization params to make sure this is working
echo "⌛ Initializing environment as follows:"
echo "Runtime UID: $PUID"
echo "Runtime GID: $PGID"
echo "Runtime User: $USERNAME"
echo "Runtime Home: $USER_HOME"
echo "Current User: $(whoami)"
echo "Current UID: $(id -u)"
echo "🚀 Let's go........."

# Execute with goso, and fallback to su (typically in development mode)
if command -v gosu >/dev/null 2>&1; then
    exec gosu "$PUID:$PGID" python3 /usr/src/tyzen9/main.py "$@"
elif command -v su-exec >/dev/null 2>&1; then
    exec su-exec "$PUID:$PGID" python3 /usr/src/tyzen9/main.py "$@"
else
    # Devcontainer: run as root
    if [ "${DEBUG:-0}" = "1" ]; then
        echo "WARNING: No gosu/su-exec → running as root (devcontainer mode)"
    fi
    exec python3 /usr/src/tyzen9/main.py "$@"
fi