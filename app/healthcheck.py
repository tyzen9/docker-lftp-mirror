import os
import sys
import time

HEARTBEAT_FILE = os.environ.get('HEARTBEAT_FILE', '/tmp/heartbeat')
UPDATE_INTERVAL = int(os.environ.get('UPDATE_INTERVAL', '300'))
STALL_TIMEOUT = int(os.environ.get('STALL_TIMEOUT', '900'))
# Buffer on top of the expected idle window (sleep between cycles, plus the
# stall timeout the watchdog allows before killing a hung transfer) to absorb
# process/scheduling jitter without flapping the healthcheck.
GRACE_PERIOD = 120

if __name__ == "__main__":
    max_age = UPDATE_INTERVAL + STALL_TIMEOUT + GRACE_PERIOD

    if not os.path.exists(HEARTBEAT_FILE):
        print(f"Heartbeat file {HEARTBEAT_FILE} not found")
        sys.exit(1)

    age = time.time() - os.path.getmtime(HEARTBEAT_FILE)
    if age > max_age:
        print(f"Heartbeat stale: {age:.0f}s old (max {max_age}s)")
        sys.exit(1)

    sys.exit(0)
