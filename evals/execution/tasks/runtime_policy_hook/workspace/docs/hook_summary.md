# Hook summary (SDK 2.1 notes)

Event order for one tool call, as documented in the 2.1 release:

1. permission_request
2. pre_tool_use
3. post_tool_use

Denied calls are not shown to the model; the recorder drops their observation.
Hooks may rewrite arguments, and the recorder marks any rewrite as mutated.
A denial never changes the workspace.

These notes were written for SDK 2.1. The policy file in `config/` is version 2.3.
