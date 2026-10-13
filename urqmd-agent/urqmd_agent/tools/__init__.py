"""UrQMD Agent tool layer.

Importing this package registers every tool in the registry. Nothing here
imports matplotlib or runs UrQMD at import time.
"""

from . import registry  # noqa: F401
from .registry import (ANALYSIS, PHYSICS_INTERVENTION, READ_ONLY,  # noqa: F401
                       REGISTRY, SIMULATION, SOURCE_MODIFICATION, ToolSpec,
                       get, register)

# tool modules: registration happens at import
from . import environment  # noqa: F401,E402
from . import source  # noqa: F401,E402
from . import simulation  # noqa: F401,E402
from . import observables  # noqa: F401,E402
from . import history  # noqa: F401,E402
from . import genealogy  # noqa: F401,E402
from . import intervention  # noqa: F401,E402
from . import validation  # noqa: F401,E402
