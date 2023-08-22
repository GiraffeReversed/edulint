import subprocess
import atexit
import os
import sys
from subprocess import PIPE, TimeoutExpired, Popen
from typing import Optional, Tuple, List
from loguru import logger

""" Author: Ondrej Borysek, License: MIT, Last update: 2021-04-19"""

SIGKILL_STATUS_CODE = 137 - 128  # -9
SIGTERM_STATUS_CODE = 143 - 128  # -15


class ProcessHandler:
    """
    This simple wrapper for subprocess library enables easier Input/Output testing of other programs.
    No pip packages or additional linux packages are required.
    Should work on Linux, Windows, and hopefully also on MacOS.
    """

    def __init__(self, timeout: float) -> None:
        self.last_child: Optional[Popen[bytes]] = None
        self.__try_to_be_nice()
        self.timeout: float = timeout
        self.sigterm_grace_period = 0.2  # second
        atexit.register(self.__kill_children)
        # Using prctl would be safer, but less portable: https://pythonhosted.org/python-prctl/#prctl.set_pdeathsig

    def __try_to_be_nice(self) -> None:
        if getattr(os, "nice", None):
            os.nice(10)

    def __kill_children(self) -> None:
        if self.last_child is None or self.last_child.poll() is not None:
            return

        logger.info("trying to terminate")
        self.last_child.terminate()  # Ask the child to exit peacefully.

        try:
            self.last_child.wait(timeout=self.sigterm_grace_period)
        except TimeoutExpired:
            logger.info("child refused to terminate; trying SIGKILL if available")
            self.last_child.kill()  # Kill anyone still standing, just like Anakin did.
            # self.last_child.wait()  # Waiting would be safe on Linux, but on Windows .kill from Python
            # is just .terminate

        if self.last_child.poll():
            try:
                _, _ = self.last_child.communicate(
                    timeout=0.2
                )  # this can garbage collect the process
            except TimeoutExpired:
                logger.warning(
                    "the process refused to die, you might need to kill the zombi manually"
                )
                ProcessHandler.linux_print_processes()

    def __start_process(
        self, user_command: List[str], input_str: Optional[str] = None
    ) -> Tuple[int, str, str]:
        # Subprocess will be with the same niceness as the main program.
        # Warning: Do NOT use shell=True. That would only kill the shell, not the C program.
        proc = subprocess.Popen(user_command, shell=False, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        self.last_child = proc

        return_code = SIGKILL_STATUS_CODE

        try:
            outb, errb = proc.communicate(
                input=input_str.encode("utf8") if input_str else None, timeout=self.timeout
            )
            return_code = proc.returncode
        except TimeoutExpired:
            logger.warning("timeout, trying to kill")
            proc.kill()
            outb, errb = proc.communicate()
            # proc.returncode will be ignored

        self.__kill_children()
        return return_code, outb.decode(), errb.decode()

    @staticmethod
    def run(
        command: List[str],
        input_str: Optional[str] = None,
        timeout: float = 5,  # seconds
    ) -> Tuple[int, str, str]:
        if command is None:
            return -1, "", "No command provided"

        ph = ProcessHandler(timeout=timeout)
        return_code, outs, errs = ph.__start_process(command, input_str=input_str)
        logger.trace(
            "Command: {command}\n"
            "Input:\n---\n{input_str}\n---\n"
            "Return code: {return_code}\n"
            "Output:\n---\n{output_str}\n---\n"
            "Error:\n---\n{error_str}\n---\n",
            command=command,
            input_str=input_str,
            return_code=return_code,
            output_str=ProcessHandler.prettyfi_the_output(outs),
            error_str=ProcessHandler.prettyfi_the_output(errs),
        )
        return return_code, outs, errs

    @staticmethod
    def prettyfi_the_output(a: str) -> str:
        return a.replace("\\r\\n", "\n").replace("\\n", "\n")

    @staticmethod
    def linux_print_processes() -> None:
        if not sys.platform.startswith("linux"):
            return
        logger.warning(
            "please check that you do not see any zombie processes from running this script, "
            "they would have nice value of 19. You can use command 'ps a -o pid,ni,time,cmd'"
        )

    @staticmethod
    def is_status_code_by_timeout(status_code: int) -> bool:
        return status_code in [SIGTERM_STATUS_CODE, SIGKILL_STATUS_CODE]
