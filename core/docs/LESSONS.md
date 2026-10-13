# Lessons retained from research

1. Clone containers inherited compose labels and could receive commands intended for the worker. Strip
   those labels, resolve the worker on the host, and verify identity before cloning.
2. Generated checks can be wrong. A passing check is evidence, not completion authority; a failing check
   must not coerce correct work into matching a false requirement. Preserve the original task.
3. Claim-free review examines state and observed actions without the solver's completion claim. Reviews
   remain fallible advice, including high-confidence objections; record errors and unanswered criteria.
4. A long reasoning turn cut by output limits may represent real work. Preserve it and surface truncation.
   Changes to recovery effort/caps affect the model and require evaluation, not just unit tests.
5. V3 substrate failures must not be mislabelled V4 model failures. Match source and exact trace identity.
6. Re-running commands or re-reading mutable files does not recover historical observations. Keep exact
   snapshots. Repeated reads are useful audit candidates, not proof that context loss caused repetition.
7. Character-prefix stability and provider cached-token shares are different measures; differences alone
   do not localize a cache defect. Offline replay cannot establish task-solving improvement.
8. Imports and test counts are not capability proof. Test real shell/file effects, known-bad cases, unknown
   accounting, cleanup, and a wheel installed outside the source tree.
9. Atomic staging is not enough: a plain mv into a directory can report success at the wrong path.
   Commit the pathname with rename semantics; test a directory appearing after preflight.
10. A terminal name identifies a live session; an output path identifies a particular generation.
   Preserve old logs when the session restarts, rather than reusing and truncating their path.
11. A high-confidence reviewer completion opinion is still not verification. The native wrong-artifact
   control must fail even when the runtime successfully submits it.
12. Generation suffixes must not collide with valid user names. Separate the namespace with a
   character the public name grammar excludes, and test live state in both names across restart.
13. Resource ownership begins before readiness. Register the launch and known PID before fallible
   initialization; retain ownership through failed stop, and resolve lost launch replies from the
   owned PID file during cleanup. Missing ownership evidence is an error, not successful cleanup.
