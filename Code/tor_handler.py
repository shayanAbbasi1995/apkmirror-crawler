import os
import subprocess
import time

from stem import Signal
from stem.control import Controller

from config import TOR_DIR, TOR_INSTANCES, TOR_PATH


def start_tor_instances():
    """Start all configured Tor instances."""
    for instance in TOR_INSTANCES:
        torrc_path = os.path.join(TOR_DIR, instance["torrc"])
        try:
            subprocess.Popen(
                [TOR_PATH, "-f", torrc_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(1)
        except Exception as e:
            print(f"Failed to start Tor on port {instance['port']}: {e}")


def renew_tor_ip(control_port):
    """Send a NEWNYM signal to rotate the Tor circuit on the given control port."""
    try:
        with Controller.from_port(port=control_port) as controller:
            controller.authenticate()
            controller.signal(Signal.NEWNYM)
            print(f"Refreshed Tor IP on control port {control_port}")
    except Exception as e:
        print(f"Failed to refresh Tor IP on port {control_port}: {e}")


def stop_tor():
    """Terminate all running Tor processes."""
    subprocess.run(
        ["taskkill", "/F", "/IM", "tor.exe"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
