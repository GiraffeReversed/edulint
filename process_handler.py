import subprocess
import atexit
import os
import sys
from subprocess import PIPE, TimeoutExpired, Popen
from typing import Optional, Tuple, List

""" Author: Ondrej Borysek, License: MIT, Last update: 2021-04-19"""


class ProcessHandler:
    """
       This simple wrapper for subprocess library enables easier Input/Output testing of other programs.
       No pip packages or additional linux packages are required.
       Should work on Linux, Windows, and hopefully also on MacOS.
       """

    def __init__(self, timeout: float) -> None:
        self.last_child : Optional[Popen[bytes]] = None
        self.__try_to_be_nice()
        self.timeout: float = timeout
        self.sigterm_grace_period = 0.2  # second
        atexit.register(self.__kill_children)
        # Using prctl would be safer, but less portable: https://pythonhosted.org/python-prctl/#prctl.set_pdeathsig

    def __try_to_be_nice(self) -> None:
        if getattr(os, 'nice', None):
            os.nice(10)

    def __kill_children(self) -> None:
        if self.last_child is None or self.last_child.poll() is not None:
            return

        print("Trying to terminate.")
        self.last_child.terminate()  # Ask the child to exit peacefully.
        
        try:
            self.last_child.wait(timeout=self.sigterm_grace_period)
        except TimeoutExpired:
            print("Child refused to terminate. Trying SIGKILL if available.")
            self.last_child.kill()  # Kill anyone still standing, just like Anakin did.
            # self.last_child.wait()  # Waiting would be safe on Linux, but on Windows .kill from Python is just .terminate

        if self.last_child.poll():
            try:
                _, _ = self.last_child.communicate(timeout=0.2)  # this can garbage collect the process
            except TimeoutExpired:
                print(f"[Warning] The process refused to die. You might need to kill the zombie manually.")
                ProcessHandler.linux_print_processes()

    def __start_process(self, user_command: List[str], input_str: Optional[str] = None) -> Tuple[int, str, str]:

        # Subprocess will be with the same niceness as the main program.
        # Warning: Do NOT use shell=True. That would only kill the shell, not the C program.
        proc = subprocess.Popen(user_command, shell=False, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        self.last_child = proc

        try:
            outb, errb = proc.communicate(input=input_str.encode("utf8") if input_str else None, timeout=self.timeout)
        except TimeoutExpired:
            print("Timeout, trying to kill.")
            proc.kill()
            outb, errb = proc.communicate()

        self.__kill_children()
        return proc.returncode, outb.decode(), errb.decode()

    @staticmethod
    def run(command: List[str],
            input_str: Optional[str] = None,
            print_output: bool = False,
            timeout: float = 5  # seconds
            ) -> Tuple[int, str, str]:
        if command is None:
            return -1, "", "No command provided"

        ph = ProcessHandler(timeout=timeout)
        return_code, outs, errs = ph.__start_process(command, input_str=input_str)
        if print_output:
            print("Command:", command)
            print("Input:\n---\n", input_str, sep="", end="---\n")
            print("Return code:", return_code)
            print("Output:\n---\n", ProcessHandler.prettyfi_the_output(outs), sep="", end="---\n")
            print("Error:\n---\n", ProcessHandler.prettyfi_the_output(errs), sep="", end="---\n\n")
        return return_code, outs, errs

    @staticmethod
    def prettyfi_the_output(a: str) -> str:
        return a.replace("\\r\\n", "\n").replace("\\n", "\n")

    @staticmethod
    def linux_print_processes() -> None:
        if not sys.platform.startswith('linux'):
            return
        print("""Please check that you don't see any zombie processes from the process of testing. They would have nice
              value of 19. You can use command "ps a -o pid,ni,time,cmd" """)


def usage_example() -> None:
    command_to_execute = ['/bin/sh', '-c', 'echo Lorem Ipsum']
    input_str = "Echo doesn't use input from stdin, but we can give it one anyway."
    return_code, outs, errs = ProcessHandler.run(command_to_execute, input_str=input_str, print_output=True)
    assert return_code == 0
    assert "Lorem Ipsum" in outs  # beware different newlines based on system
    assert len(errs) == 0


def usage_example_different_timeout() -> None:
    command_to_execute = ['/bin/sh', '-c', 'while true; do sleep 1; done;']
    return_code, outs, errs = ProcessHandler.run(command_to_execute, print_output=True, timeout=0.5)
    assert return_code == -9  # SIGKILL


if __name__ == "__main__":
    # Examples are presuming you're running Linux. If that's not the case, just edit the commands and arguments for
    # their Windows/other OS alternatives.
    usage_example()
    usage_example_different_timeout()
