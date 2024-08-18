from typing import Dict
import os
from threading import Thread
from pathlib import Path
from typing import Optional, Dict
import dbm
import time
import random

import tomli
import requests
from platformdirs import PlatformDirs
from loguru import logger


SCRIPT_PATH = os.path.dirname(os.path.abspath(__file__))
EXPLANATIONS_PIP_DISTRIBUTED_FILEPATH = os.path.join(SCRIPT_PATH, "explanations.toml")

EDULINT_LOCAL_DATA_FOLDER = PlatformDirs(appname="edulint").user_data_dir
EXPLANATIONS_ONLINE_DISTRIBUTED_FILEPATH = os.path.join(EDULINT_LOCAL_DATA_FOLDER, "explanations_online.toml")
EXPLANATIONS_DBM = os.path.join(EDULINT_LOCAL_DATA_FOLDER, "explanations.dbm")
GITHUB_URL = "https://raw.githubusercontent.com/GiraffeReversed/edulint/main/edulint/explanations.toml"

try:
    Path(EDULINT_LOCAL_DATA_FOLDER).mkdir(parents=True, exist_ok=True)
except Exception as e:
    logger.warning("Failed to create local directory for edulints internal files. {e}")

# --- Read explanations
def get_explanations(disable_explanations_update: bool = False) -> Dict[str, Dict[str, str]]:
    update_explanations(disable_explanations_update)  # This is async. Its results won't be ready during the lifetime of this function.

    updated_explanations = _load_updated_explanations()
    if updated_explanations:
        return updated_explanations

    with open(EXPLANATIONS_PIP_DISTRIBUTED_FILEPATH, "rb") as f:
        parsed_toml = tomli.load(f)
    return parsed_toml


def _load_updated_explanations() -> Optional[Dict[str, str]]:
    path_for_online_file = Path(EXPLANATIONS_ONLINE_DISTRIBUTED_FILEPATH)
    if not path_for_online_file.exists():
        return
    try:
        with open(EXPLANATIONS_PIP_DISTRIBUTED_FILEPATH, "rb") as f:
            return tomli.load(f)
    except:
        logger.warning("Updated explanations seem to be corrupted. Falling back to those distributed with the pip package.")


# --- Update explanation
def current_timestamp() -> int:
    return int(time.time())


def update_explanations(disable_explanations_update: bool = False):
    if disable_explanations_update:
        return
    Thread(target=_thread_update_explanations).start()


def _thread_update_explanations(ttl: int = 600): 
    try:
        if not Path(EXPLANATIONS_DBM).exists():
            time.sleep(random.randint(1,30)/1000)  # Small random delay to lower the chance for file creation race condition 
        with dbm.open(EXPLANATIONS_DBM, 'c') as db:
            if current_timestamp() < int(db.get('last_update', b'0')) + ttl:
                return
            db['last_update'] = str(current_timestamp())  # We're counting any update attempt, not just the succesfull ones
        logger.debug(f"Succesfully wrote current time to {EXPLANATIONS_DBM}.")

        resp = requests.get(GITHUB_URL, timeout=3)
        if resp.status_code != 200:
            return

        with open(EXPLANATIONS_ONLINE_DISTRIBUTED_FILEPATH, "w", encoding="utf8") as f:
            f.write(resp.text)
    except Exception as e:
        logger.debug(f"Update of explanations failed with {e}. This can ocassionaly hapen for some processes due to race condition.")

# todo: add test to load explanantions (toml parser is sensitive to small mistakes)

if __name__ == "__main__":
    get_explanations()
