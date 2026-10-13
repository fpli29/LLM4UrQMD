"""Runtime configuration for the Agent tool layer.

The default event cap exists so that an LLM agent cannot accidentally
launch high-statistics production. It can only be raised by an explicit,
caller-supplied authorization value; tools pass it through and the
guardrail enforces it.
"""

DEFAULT_EVENT_CAP = 100

# Bootstrap seed used by Phase 1B/1B2 reproduction checks.
BOOTSTRAP_SEED_REPRO = 20260919
# Bootstrap seed preregistered for intervention-era comparisons.
BOOTSTRAP_SEED_INTERVENTION = 20260920

DEFAULT_ECM = 7.7
