
# <img src="doc/images/t9_logo.png" height="25"> Tyzen9 - docker-lftp-mirror
This ia a container is excellent for mirroring the contents of a source server to a target server using an `ssh` tunnel and `lftp` to perform efficient file transfers through a secure connection. 

This container is specifically designed to PULL data from a source server, to a target server and mirror the contents of the source server.

> [!WARNING]
> This means that deleted files on the source server, will also be deleted on the target server as a result of the mirroring process.

LFTP is a sophisticated, command-line file transfer program designed for Unix and Unix-like operating systems, such as Linux. It supports a wide range of protocols, including FTP, FTPS, HTTP, HTTPS, and SFTP, making it a versatile tool for transferring files between local and remote systems. Unlike traditional FTP clients that rely on graphical interfaces, LFTP operates entirely through the command line, offering a lightweight and scriptable alternative.

Using LFTP has the following benefits:

- Parallel file transfers, which can significantly speed up operations when handling multiple files or large datasets
- Automatic resumption of interrupted transfers
- Retry mechanisms for non-fatal errors

## Supported Architectures
Simply pulling `tyzen9/lftp-mirror:latest` should retrieve the correct image for your arch. The architectures supported by this image are:

| Architecture | Available | Tag |
| :---   | :--- | :--- |
| x86-64 | ✅ | latest |
| arm64	 | ✅ | latest |

Specific version tags are available on [Docker Hub](https://hub.docker.com/repository/docker/tyzen9/lftp-mirror/tags).

# Deployment
The recommended means of deploying this container is through Docker compose.  The `compose.yml` file provides an excellent example of this. Below you will see an example of this:

```yaml
services:
  lftp-mirror:
    image: tyzen9/lftp-mirror:latest
    container_name: lftp-mirror
    environment:
      - TZ_ID=${TZ_ID}
      - PUID=${PUID:-1000}
      - PGID=${PGID:-1000}
      - SOURCE_HOSTNAME=${SOURCE_HOSTNAME}
      - SSH_USERNAME=${SSH_USERNAME}
      - SSH_PASSWORD=${SSH_PASSWORD}
      - SOURCE_DIR=${SOURCE_DIR}
      - SOURCE_EXCLUDES=${SOURCE_EXCLUDES}
    volumes:
      - ${LOCAL_TARGET_DIR}:/downloads
```

## Required Configuration Options
These environment variables MUST be defined:
| Variable | Type | Example | Definition |
| :---   | :--- | :--- | :--- |
| SOURCE_HOSTNAME | string | host.domain.com | The name of the server to connect with |
| SSH_USERNAME | string | \<username\> | The ssh username used to connect to the source server |
| SSH_PASSWORD | string | \<password\> | The ssh password used to  connect to the source server |
| SOURCE_DIR | string | \downloads | The path to the directory to mirror on the source server |

## Optional Configuration Options
These environment variables are optional, and could be used to adjust functionality:
| Variable | Type | Default | Definition |
| :---   | :--- | :--- | :--- |
| TZ_ID | string | UTC | Timezone to be running this container as [TZ IDs](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones#List) |
| PUID | number | 1000 | The linux user ID to run this process as |
| PGID | number | 1000 | The linux group ID to run this process as |
| UPDATE_INTERVAL | string | 300 | The number of seconds between LFTP initiated requests |
| SOURCE_EXCLUDES | string | "\<empty\>" | A comma separated lists of sources to exclude, [see here](https://www.cyberciti.biz/faq/lftp-command-mirror-x-exclude-files-sub-directory-syntax/) for details. (Example: temp/,freeleech/) |
| SSH_PORT | string | 22 | The ssh port used to  connect to the source server |
| LOG_LEVEL | string | INFO | Valid values: DEBUG, INFO, WARNING, ERROR, CRITICAL  |

# Development
This project is designed to be developed with VS code and the [Dev Containers](https://marketplace.visualstudio.com/items/?itemName=ms-vscode-remote.remote-containers) extension. When testing LFTP transfers, the development environment is set to mirror a provided source server with the local `downloads` file.

> [!IMPORTANT]
> In development, a `.env` file is expected. You can copy `sample.env` to make a `.env` file for testing.

## Development Environment Requirements
- Docker Engine 
- Docker Desktop (optional)
- Make - used to build and publish images

## VS Code
The following extensions are recommended to be installed in VS Code:

- [Dev Containers](https://marketplace.visualstudio.com/items/?itemName=ms-vscode-remote.remote-containers)
- [Docker](https://marketplace.visualstudio.com/items/?itemName=ms-azuretools.vscode-docker)
- [Python](https://marketplace.visualstudio.com/items/?itemName=ms-python.python)

### Open the project in a Docker Dev Container for development using VS Code
1. Install the Recommended extensions (above):
2. Ensure Docker Desktop (or another Docker service) is running on your system.
3. In VS Code, Open the Command Palette (Ctrl+Shift+P or Cmd+Shift+P), and Select `Dev Containers: Reopen in Container`
    - VS Code will build the container based on the `.devcontainer/devcontainer.json` configuration 
      The first build might take some time, but subsequent openings will be faster.
7. Develop Inside the Container. 
    - Once connected, you can use all of VS Code's features (e.g., IntelliSense, debugging) as if working locally.

To start the project in the resulting dev container issue this command line is a VSCode terminal:

```
python3 /usr/src/tyzen9/main.py 
```

> [!IMPORTANT]
> There is no hot reload configured, each time you update main.py, you need to run `Rebuild Container` in Dev Container.


## Build & Publish
Update the `Makefile` to contain the appropriate Docker Hub username, application name and version number

```
DOCKER_USERNAME ?= username
APPLICATION_NAME ?= application-name
VERSION ?= 1.0.0
```

To build images of this container, use this command in the root directory of the project:

```
make build
```

To publish th built images to to Docker Hub use this command in the root directory of the project:

To build use this command:
```
make push
```

# References
[Setting up a dockerized Python environment the elegant way](https://towardsdatascience.com/setting-a-dockerized-python-environment-the-elegant-way-f716ef85571d/)
