"""Service layer: dataset access and the Groq LLM client.

These modules isolate I/O-bound dependencies (the filesystem and the Groq API)
behind narrow seams so the agents can stay pure and testable.
"""
