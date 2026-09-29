"""Rick's entry point (see Run Rick.bat). Kept deliberately tiny: everything
that can fail at import time (audio libraries, the Gemini SDK, .env
parsing) is imported only inside run(), after logging and the error dialog
are ready - Rick has no console, so otherwise such failures are silent."""

from rick.startup import run


def _start() -> None:
    from rick.app import main

    main()


if __name__ == "__main__":
    run(_start)
