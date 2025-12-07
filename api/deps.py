from functools import lru_cache
from agents.pipeline import HealthcarePipeline


@lru_cache # Cached with LRU so it persists across API calls.
# Singleton pattern for HealthcarePipeline instance
# Ensures high performance by reusing the same instance across API calls 
def get_pipeline() -> HealthcarePipeline:
    return HealthcarePipeline() 
