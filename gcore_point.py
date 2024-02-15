# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import gdb


class GDBEventOneShot():
    """Registers an event into the registry that runs once."""

    def __init__(self, registry, continue_after_run=True):
        """Connects the event to the provided registry.

        Arguments:
            registry: A GDB event registry, i.e. gdb.events.stop.

        Named Arguments:
            continue_after_run: Whether gdb execution should
            continue after the event completes.
        """
        self._registry = registry
        self._continue = continue_after_run

        self._registry.connect(self)

    def __call__(self, event):
        """Implements the callable interface that gdb 
        notifies of events.

        Arguments:
            event: Argument necessary for event registration.

        Docs: https://sourceware.org/gdb/current/onlinedocs/gdb.html/Events-In-Python.html
        """

        """Calls the run_event method on this instance. This
        should be implemented by the child class. It is
        wrapped in a try-except to ensure the event is still
        properly disconnected from the registry even on
        exception.
        """
        force_stop = False
        try:
            self.run_event()
        except e:
            print(e)
            force_stop = True

        self._registry.disconnect(self)

        """If the one-shot is intended to continue and no
        exception occurred in run_event, tell gdb to continue.
        """
        if not force_stop and self._continue:
            gdb.execute("continue")


class GCoreOnStop(GDBEventOneShot):
    """A one-shot event that generates a coredump on execution."""

    def __init__(self, file_name):
        """Create the oneshot event.

        Arguments:
            file_name: The name of the file to use as argument to
            gcore command.
        """
        super().__init__(gdb.events.stop)
        self._file_name = file_name

    def run_event(self):
        """Implementing the run_event method that the parent class
        requires. Executes gcore with the requested filename.
        """
        gdb.execute(f"gcore {self._file_name}")


class CoreDumpBP(gdb.Breakpoint):
    """A breakpoint that generates a core file and continues when hit."""

    def __init__(self, spec, core_name=None):
        """Set the new breakpoint.
        
        Arguments:
            spec: A GDB breakpoint spec.

        Named Arguments:
            core_name: A name for the core files generated, will be added to
                       the generated core file.
        """
        self._core_name = core_name
        super(CoreDumpBP, self).__init__(spec)

    def stop(self):
        """Executes when a breakpoint is hit.

        The core file generated has the following format if there was 
        no core_name provided:
        `core.<pid>.<count of times this breakpoint has hit>`
        So for an inferior process with pid 69, this breakpoint hit 3
        times would generate the following core files:
        `core.69.0`
        `core.69.1`
        `core.69.2`
                
        If a core_name was provided to the breakpoint, then it will be
        included in the generated core file name:
        `core.<core name>.<pid>.<count of times this breakpoint has hit>`
        """
        inferior = gdb.selected_inferior()
        core_name_prefix = f"{self._core_name}." if self._core_name is not None else ""
        core_file_name = f"core.{core_name_prefix}{inferior.pid}.{self.hit_count}"

        """Register a one-shot event that generates a coredump with the
        requested file name.
        """
        GCoreOnStop(core_file_name)

        """Returning True from the stop method signals gdb to stop. This is
        necessary because gdb's stopping process is what sets the inferior
        for the necessary ptrace calls for core dumping.

        Docs: https://sourceware.org/gdb/current/onlinedocs/gdb.html/Breakpoints-In-Python.html
        """
        return True


class GcorePointCmd(gdb.Command):
    """Generate a new breakpoint that will automatically generate a core file when hit.

    Usage:
        gcore-point spec [, core name]

    Arguments:
        spec: The breakpoint location specified in the usual breakpoint spec format.
        core name (optional): A set name to include as part of the generated core file name.
    """

    def __init__(self):
        """Installs the command. Currently the command is always called `gcore-point`
        and will always be under the `breakpoints` category.
        """
        self._name = "gcore-point"
        super(GcorePointCmd, self).__init__(self._name, gdb.COMMAND_BREAKPOINTS)

    def invoke(self, arg, from_tty):
        """Executes when the command is invoked.

        Implementing from parent class, see docs for arguments:
        https://sourceware.org/gdb/current/onlinedocs/gdb.html/CLI-Commands-In-Python.html#CLI-Commands-In-Python
        """
        if arg == "":
            raise gdb.GdbError(f"The {self._name} command must be called with arguments.")

        argv = arg.split(" ")
        spec = argv[0]
        if len(argv) > 1: 
            CoreDumpBP(spec, core_name=argv[1])
        else:
            CoreDumpBP(spec)

        return None


GcorePointCmd()

