import os
import sys
import re
import subprocess
import time
import logging
from colorlog import ColoredFormatter

###########################################
# Process environment variables
###########################################
SSH_USERNAME = os.getenv("SSH_USERNAME")
SSH_PASSWORD = os.getenv("SSH_PASSWORD")
SOURCE_EXCLUDES = os.getenv("SOURCE_EXCLUDES")
SOURCE_DIR = os.getenv("SOURCE_DIR")
TARGET_DIR = "/downloads"
SOURCE_HOSTNAME = os.getenv("SOURCE_HOSTNAME")
SSH_PORT = int(os.environ.get('SSH_PORT', '22')) # Default 22 mins
UPDATE_INTERVAL = int(os.environ.get('UPDATE_INTERVAL', '300')) # Default 5 mins

# Validate that all required environment variables are set
required_vars = {
    "SSH_USERNAME": SSH_USERNAME,
    "SSH_PASSWORD": SSH_PASSWORD,
    "EXCLUDES": SOURCE_EXCLUDES,
    "SOURCE_DIR": SOURCE_DIR,
    "TARGET_DIR": TARGET_DIR,
    "SOURCE_HOSTNAME": SOURCE_HOSTNAME,
}
missing_vars = [key for key, value in required_vars.items() if not value]
if missing_vars:
    print(f"Error: Missing required environment variables: {missing_vars}")
    sys.exit(1)

# Determine the log level to be used, the default will be INFO
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
if LOG_LEVEL not in ['DEBUG','INFO','WARNING','ERROR','CRITICAL']:
    LOG_LEVEL = 'INFO'

###########################################
# Setup Logging
###########################################
# Create a logger
#logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger()
loglevel = logging.getLevelName(LOG_LEVEL)
logger.setLevel(loglevel)

# Create formatter and add it to the handler
formatter = ColoredFormatter(
    "%(log_color)s%(asctime)s [%(levelname)s] %(message)s",
    datefmt='%Y-%m-%d %H:%M:%S',
    reset=True,
    log_colors={
        'DEBUG':    'light_black',
        'INFO':     'white',
        'WARNING':  'yellow',
        'ERROR':    'red',
        'CRITICAL': 'red,bg_white',
    },
    secondary_log_colors={},
    style='%'
)

# Create a stream handler for formatting, and initiate the format
handler = logging.StreamHandler()
handler.setFormatter(formatter)
# Add the handler to the logger
logger.addHandler(handler)

###########################################
# Functions
###########################################

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def splashLogo():
    """
    Print the splash screen to the logs
    """
    logging.info(f'''
 _____                                                          _____ 
( ___ )                                                        ( ___ )
 |   |~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~|   | 
 |   |                                                          |   | 
 |   |   ████████╗██╗   ██╗███████╗███████╗███╗   ██╗ █████╗    |   | 
 |   |   ╚══██╔══╝╚██╗ ██╔╝╚══███╔╝██╔════╝████╗  ██║██╔══██╗   |   | 
 |   |      ██║    ╚████╔╝   ███╔╝ █████╗  ██╔██╗ ██║╚██████║   |   | 
 |   |      ██║     ╚██╔╝   ███╔╝  ██╔══╝  ██║╚██╗██║ ╚═══██║   |   | 
 |   |      ██║      ██║   ███████╗███████╗██║ ╚████║ █████╔╝   |   | 
 |   |      ╚═╝      ╚═╝   ╚══════╝╚══════╝╚═╝  ╚═══╝ ╚════╝    |   | 
 |   |                https://github.com/tyzen9                 |   | 
 |   |                    Made in the U.S.A.                    |   | 
 |___|~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~|___| 
(_____)                                                        (_____)

''')

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def split_with_escaped_commas(input_string):
    result = []
    current = []
    #remove unescaped quotes
    input_string = re.sub(r'(?<!\\)["\']', '', input_string)

    i = 0
    while i < len(input_string):
        char = input_string[i]
        if char == "\\" and i + 1 < len(input_string) and input_string[i + 1] == ",":
            # Found an escaped comma, keep it...
            current.append("\\,")
            i += 2  # Skip the \ and the comma
        elif char == ",":
            # Found a non-escaped comma, finish the current segment
            result.append("".join(current))
            current = []
            i += 1
        else:
            # Add the character to the current segment
            current.append(char)
            i += 1
    # Add the last segment if there is one
    if current:
        result.append("".join(current))
    return result

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def main():

    # Acquire the host key 
    logging.info(f"Acquiring host key from {SOURCE_HOSTNAME}...")
    keyscan_command = f"ssh-keyscan -p {SSH_PORT} {SOURCE_HOSTNAME} >> ~/.ssh/known_hosts"
    try:
        result = subprocess.run(keyscan_command, check=True, text=True, capture_output=True, shell=True)
    except subprocess.CalledProcessError as e:
        logging.fatal(f"Command failed with exit code {e.returncode}")
        logging.fatal(f"Errors: {e.stderr}")
        sys.exit(1)

    # If the target directory does not exist then warn the user and create it
    if ({os.path.exists(TARGET_DIR)}):
        print(f"lftp will be synronized from {SOURCE_HOSTNAME} to this download path [{TARGET_DIR}]")
    else:
        logging.warning(f"Download Path: [{TARGET_DIR}] does not exist. Make sure an existing volume is configured, attempting to make the full path.")
        # Create the target directory if it doesn't exist
        try:
            os.makedirs(TARGET_DIR, exist_ok=True) 
            logging.info(f"Target directory set: [{TARGET_DIR}]")
        except Exception as e:
            logging.fatal(f"Failed to create target directory: [{TARGET_DIR}]: {e}")
            sys.exit(1)

    # Split the excludes string into a list of directories, and builds the appropriate command parameters
    exclude_dirs = split_with_escaped_commas(SOURCE_EXCLUDES)
    exclude_string = " ".join(f'--exclude {dir}' for dir in exclude_dirs if dir)
    logging.info(exclude_string)

    # Construct the lftp command
    lftp_command = f"/usr/bin/lftp -u {SSH_USERNAME},{SSH_PASSWORD} -e \"mirror --continue --verbose --delete --parallel=5 --use-pget-n=5 {exclude_string} {SOURCE_DIR} {TARGET_DIR}; quit\" sftp://{SOURCE_HOSTNAME}:{SSH_PORT}"

    while True:
        logging.info(f'---------------------------------------------------------')
        logging.debug(f"Command to execute \"{lftp_command}\"")

        # Run the command
        try:
            result = subprocess.run(lftp_command, check=True, text=True, capture_output=True, shell=True)
            logging.info(f"Output: {result.stdout}")
            logging.info(f"Errors (if any): {result.stderr}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Command failed with exit code {e.returncode}")
            logging.error(f"Errors: {e.stderr}")

        # Wait the set amount of time, and try updating again
        logging.info(f'---------------------------------------------------------')
        logging.info(f'Attempt another update in {UPDATE_INTERVAL} seconds')
        time.sleep(UPDATE_INTERVAL)

###########################################
# Main
###########################################

# Was this script called directly?  Then lets go....
if __name__=="__main__": 
    splashLogo()
    main()