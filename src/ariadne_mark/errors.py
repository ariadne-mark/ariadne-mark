"""Operational errors are failures, never evidence that a mark is absent."""


class AriadneError(RuntimeError):
    pass


class UnsupportedMedia(AriadneError):
    pass


class MissingModel(AriadneError):
    pass


class VerificationFailed(AriadneError):
    pass


class VerificationTimeout(AriadneError):
    """A bounded verification job did not finish; never a negative verdict."""


class C2paRuntimeMismatch(AriadneError):
    """The installed/loaded C2PA pair is not the qualified runtime."""
    def __init__(self, report):
        self.report = report
        expected = report.get('expected', {})
        super().__init__(
            'C2PA runtime not qualified (' + str(report.get('reason')) + '); expected '
            + str(expected.get('python_package')) + ' / native '
            + str(expected.get('native_version')) + ' on '
            + str(expected.get('platform')) + '; observed '
            + str(report.get('python_package')) + ' / native '
            + str(report.get('native_version'))
            + '. Use the qualified Linux image or run python -m ariadne_mark.bootstrap_c2pa'
              ' in a supported Python 3.12 environment, then restart the process.')
