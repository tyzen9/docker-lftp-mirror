import os
import sys
import re
import subprocess
import threading
import time
import logging
from datetime import datetime, timedelta
from colorlog import ColoredFormatter

import web

###########################################
# Process environment variables
###########################################
SSH_USERNAME = os.getenv("SSH_USERNAME")
SSH_PASSWORD = os.getenv("SSH_PASSWORD")
SOURCE_EXCLUDES = os.getenv("SOURCE_EXCLUDES")
SOURCE_DIR = os.getenv("SOURCE_DIR")
TARGET_DIR = "/downloads"
SOURCE_HOSTNAME = os.getenv("SOURCE_HOSTNAME")
SSH_PORT = int(os.environ.get('SSH_PORT', '22'))
UPDATE_INTERVAL = int(os.environ.get('UPDATE_INTERVAL', '300'))

# Heartbeat file used by healthcheck.py to detect a hung sync. Touched at the
# start of every cycle and on every line of lftp output, so a stalled SFTP
# connection (no output, no progress) shows up as a stale heartbeat.
HEARTBEAT_FILE = os.environ.get('HEARTBEAT_FILE', '/tmp/heartbeat')
# How long to wait with no lftp output before treating the transfer as stalled
# and killing it, rather than hanging forever on a dead connection.
STALL_TIMEOUT = int(os.environ.get('STALL_TIMEOUT', '900'))

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
def touch_heartbeat():
    """Record proof of life/progress for healthcheck.py to read."""
    try:
        with open(HEARTBEAT_FILE, "a"):
            os.utime(HEARTBEAT_FILE, None)
    except OSError as e:
        logging.debug(f"Failed to touch heartbeat file: {e}")

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def run_lftp(command):
    """Run lftp and stream output in real time, logging file transfer events.
    A watchdog thread kills the lftp process if no output is seen for
    STALL_TIMEOUT seconds — otherwise a dropped/stalled SFTP connection can
    leave process.wait() blocked forever with no way to recover.
    """
    current_file = None
    downloaded = 0
    removed = 0

    def drain_stdout(pipe):
        nonlocal current_file, downloaded, removed
        for line in pipe:
            touch_heartbeat()
            line = line.rstrip()
            if not line:
                continue
            transfer_match = re.match(r"Transferring file `(.+)'", line)
            remove_match = re.match(r"Removing old (?:file|directory) `(.+)'", line)
            mkdir_match = re.match(r"mkdir `(.+)'", line)
            if transfer_match:
                if current_file:
                    downloaded += 1
                    logging.info(f"    ☑️  Completed: {current_file}")
                    web.record_event("download", current_file)
                current_file = transfer_match.group(1)
                logging.info(f"  🟢 Downloading: {current_file}")
            elif remove_match:
                removed += 1
                logging.info(f"  🗑️  Removing:   {remove_match.group(1)}")
                web.record_event("remove", remove_match.group(1))
            elif mkdir_match:
                logging.info(f"  📁 mkdir:      {mkdir_match.group(1)}")
            else:
                logging.debug(f"lftp: {line}")
        if current_file:
            downloaded += 1
            logging.info(f"    ☑️  Completed: {current_file}")
            web.record_event("download", current_file)

    def drain_stderr(pipe):
        for line in pipe:
            touch_heartbeat()
            line = line.rstrip()
            if line:
                logging.warning(f"lftp: {line}")

    def watch_for_stall(process, stop_event):
        while not stop_event.wait(15):
            age = time.time() - os.path.getmtime(HEARTBEAT_FILE)
            if age > STALL_TIMEOUT:
                logging.error(f"⚠️  No lftp progress for {int(age)}s — killing stalled transfer")
                process.kill()
                return

    touch_heartbeat()
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, shell=True, bufsize=1
    )
    stop_event = threading.Event()
    t_out = threading.Thread(target=drain_stdout, args=(process.stdout,))
    t_err = threading.Thread(target=drain_stderr, args=(process.stderr,))
    t_watch = threading.Thread(target=watch_for_stall, args=(process, stop_event))
    t_out.start()
    t_err.start()
    t_watch.start()
    process.wait()
    stop_event.set()
    t_out.join()
    t_err.join()
    t_watch.join()
    return process.returncode, downloaded, removed

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def main():

    # Seed the heartbeat immediately so healthcheck.py has something to read
    # before the first cycle completes.
    touch_heartbeat()

    # Serve /status and /events for external consumers (e.g. a Home
    # Assistant RESTful sensor) over HTTP.
    web.start_server()

    # Acquire the host key
    logging.info(f"🔑 Acquiring host key from {SOURCE_HOSTNAME}...")
    keyscan_command = f"ssh-keyscan -p {SSH_PORT} {SOURCE_HOSTNAME} >> ~/.ssh/known_hosts"
    try:
        result = subprocess.run(keyscan_command, check=True, text=True, capture_output=True, shell=True, timeout=30)
    except subprocess.TimeoutExpired:
        logging.fatal(f"Timed out waiting for ssh-keyscan against {SOURCE_HOSTNAME}")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        logging.fatal(f"Command failed with exit code {e.returncode}")
        logging.fatal(f"Errors: {e.stderr}")
        sys.exit(1)

    # If the target directory does not exist then warn the user and create it
    if ({os.path.exists(TARGET_DIR)}):
        logging.info(f"🔗 Source:   {SSH_USERNAME}@{SOURCE_HOSTNAME}:{SOURCE_DIR}")
        logging.info(f"📂 Target:   {TARGET_DIR}")
    else:
        logging.warning(f"Download Path: [{TARGET_DIR}] does not exist. Make sure an existing volume is configured, attempting to make the full path.")
        try:
            os.makedirs(TARGET_DIR, exist_ok=True)
            logging.info(f"🔗 Source:   {SSH_USERNAME}@{SOURCE_HOSTNAME}:{SOURCE_DIR}")
            logging.info(f"📂 Target:   {TARGET_DIR}")
        except Exception as e:
            logging.fatal(f"Failed to create target directory: [{TARGET_DIR}]: {e}")
            sys.exit(1)

    # Split the excludes string into a list of directories, and builds the appropriate command parameters
    exclude_dirs = split_with_escaped_commas(SOURCE_EXCLUDES)
    exclude_string = " ".join(f'--exclude {dir}' for dir in exclude_dirs if dir)
    logging.info(f"🚫 Excludes: {', '.join(d for d in exclude_dirs if d)}")

    # Construct the lftp command
    lftp_command = f"/usr/bin/lftp -u {SSH_USERNAME},{SSH_PASSWORD} -e \"mirror --continue --verbose --delete --parallel=5 --use-pget-n=5 {exclude_string} {SOURCE_DIR} {TARGET_DIR}; quit\" sftp://{SOURCE_HOSTNAME}:{SSH_PORT}"
    # FIX: Pass lftp_command as a list to eliminate shell=True
    # lftp_command = [
    #     '/usr/bin/lftp', '-u', f'{SSH_USERNAME},{SSH_PASSWORD}',
    #     '-e', f'mirror --continue --verbose --delete --parallel=5 --use-pget-n=5 {exclude_string} {SOURCE_DIR} {TARGET_DIR}; quit',
    #     f'sftp://{SOURCE_HOSTNAME}:{SSH_PORT}'
    # ]

    cycle = 0
    while True:
        cycle += 1
        header = f'--- Sync #{cycle} '
        logging.info(header + '-' * max(0, 57 - len(header)))
        logging.debug(f"Command to execute \"{lftp_command}\"")
        web.update_state(cycle=cycle, last_sync_start=time.time())

        # Run the command
        try:
            returncode, downloaded, removed = run_lftp(lftp_command)
            if returncode != 0:
                logging.error(f"lftp failed with exit code {returncode}")
                web.update_state(last_error=f"lftp exited with code {returncode}")
            else:
                logging.info(f"✅ Sync complete — {downloaded} downloaded, {removed} removed")
                web.update_state(last_error=None)
            web.update_state(
                downloaded=downloaded, removed=removed,
                last_sync_end=time.time(), last_sync_success=(returncode == 0),
            )
        except Exception as e:
            logging.error(f"Failed to run lftp: {e}")
            web.update_state(last_error=str(e), last_sync_success=False, last_sync_end=time.time())

        next_run = datetime.now() + timedelta(seconds=UPDATE_INTERVAL)
        logging.info(f"⏳ Next sync at {next_run.strftime('%H:%M:%S')}")
        web.update_state(next_sync=next_run.isoformat())
        touch_heartbeat()
        time.sleep(UPDATE_INTERVAL)

###########################################
# Main
###########################################

# Was this script called directly?  Then lets go....
if __name__=="__main__":
    splashLogo()
    main()
