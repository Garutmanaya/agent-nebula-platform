"""Agent Nebula integration layer for the official A2A SDK.

Keep this package initializer side-effect free.  Configuration, security and
runtime modules import one another through explicit submodules; eagerly
importing the server here creates cycles while Platform presets are loading.
"""

__all__: list[str] = []
