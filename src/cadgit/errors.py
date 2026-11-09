class CadgitError(Exception):
    """An actionable error that the CLI and UI can present without a traceback."""


class PublishedWriteError(OSError):
    """The destination is visible, but durability or cleanup could not finish."""

    def __init__(self, destination: str, cause: OSError) -> None:
        self.destination = destination
        self.cause = cause
        super().__init__(
            f"Published {destination}; completion could not be confirmed: {cause}"
        )
