"""Lambda handlers - one per stage of the pipeline.

Each handler is a thin wrapper that:
1. Parses the incoming event
2. Instantiates the corresponding BaseLambda subclass
3. Calls its handle() method
4. Returns the result to Step Function
"""

# Phase 1 handler files:
# - detect_handler.py
# - parse_handler.py
# - chunk_handler.py
# - redact_handler.py
# - embed_handler.py
# - classify_handler.py
# - route_handler.py
# - search_handler.py
# - feedback_handler.py
