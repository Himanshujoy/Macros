"""Errors the commands report to the owner in plain words."""


class MacroError(Exception):
    """Any failure a command reports as a plain message, without a traceback."""


class SourceError(MacroError):
    """A data source failed or returned something unexpected."""


class BuildError(MacroError):
    """The output folder could not be built."""


class AnalysisError(MacroError):
    """The analysis file is missing, or fails its checks."""
