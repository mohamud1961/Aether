"""Aether Core: a lean agent loop that maximises the model.

The model gets persistent terminals, file tools, full outputs kept on disk and a
visible clock; the harness keeps time, records everything and optionally asks an
independent verifier (the reviewer) to review the final workspace state. Nothing else.
"""
