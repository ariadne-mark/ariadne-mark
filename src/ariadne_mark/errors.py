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
