from __future__ import annotations

import os
from functools import lru_cache

from langfuse import get_client


@lru_cache(maxsize=1)
def get_langfuse_client(environment):
    os.environ["LANGFUSE_TRACING_ENVIRONMENT"] ="prod" if environment == "prod" else "eval"
    return get_client()