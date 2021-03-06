import subprocess
import re
import shlex
import sys
import os

class Base:
    """
        This is the base search engine class.
        Override it to define new search engines.
    """

    SETTINGS = [
        "path_to_executable",
        "mandatory_options",
        "common_options"
    ]

    HAS_COLUMN_INFO = re.compile('^[^:]+:\d+:\d+:')

    def __init__(self, settings):
        """
            Receives the sublime.Settings object
        """
        self.settings = settings
        for setting_name in self.__class__.SETTINGS:
            setting_value = self.settings.get(self._full_settings_name(setting_name), '')
            if sys.version < '3':
                setting_value = setting_value.encode()
            setattr(self, setting_name, setting_value)
        if os.name=='nt':
            self._resolve_windows_path_to_executable()

    def run(self, query, folders):
        """
            Run the search engine. Return a list of tuples, where first element is
            the absolute file path, and optionally row information, separated
            by a semicolon, and the second element is the result string
        """
        arguments = self._arguments(query, folders)
        print("Running: %s" % " ".join(arguments))

        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            pipe = subprocess.Popen(arguments,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=folders[0],
                startupinfo=startupinfo
                )
        except OSError: # Not FileNotFoundError for compatibility with Sublime Text 2
            raise RuntimeError("Could not find executable %s" % self.path_to_executable)

        output, error = pipe.communicate()

        if self._is_search_error(pipe.returncode, output, error):
            raise RuntimeError(self._sanitize_output(error))
        return self._parse_output(self._sanitize_output(output))

    def _arguments(self, query, folders):
        """
            Prepare arguments list for the search engine.
        """
        return (
            [self.path_to_executable] +
            shlex.split(self.mandatory_options) +
            shlex.split(self.common_options) +
            [query] +
            folders)

    def _sanitize_output(self, output):
        return output.decode('utf-8', 'ignore').strip().replace("\\", "/")

    def _parse_output(self, output):        
        #print("Parsing: %s" % " ".join(output))
        lines = output.split("\n")
        drive = lines[0][0:2]
        line_parts = [line[2:].split(":", 3) if Base.HAS_COLUMN_INFO.match(line[2:]) else line[2:].split(":", 2) for line in lines]
        line_parts = self._filter_lines_without_matches(line_parts)
        return [(drive + "|".join(line[0:-1]), line[-1].strip()) for line in line_parts]

    def _is_search_error(self, returncode, output, error):
        returncode != 0

    def _full_settings_name(self, name): 
        return "search_in_project_%s_%s" % (self.__class__.__name__, name)

    def _filter_lines_without_matches(self, line_parts):
        return filter(lambda line: len(line) > 2, line_parts)

    def _resolve_windows_path_to_executable(self):
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            self.path_to_executable = self._sanitize_output(subprocess.check_output("where %s" % self.path_to_executable, startupinfo=startupinfo))
        except subprocess.CalledProcessError:
            # do nothing, executable not found
            pass
        except sys.FileNotFoundError:
            # do nothing, executable not found
            pass
