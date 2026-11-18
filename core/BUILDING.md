# How I build Core

The aim is to move fast without fooling myself. Every change is a small experiment: cheap to try, quick to
measure and easy to remove.

## The loop

1. **Ask one question and write down the expected answer.** For example: "Will writing the run's state once,
   instead of every turn, cut cost without losing passes?" The prediction is written before anything runs.
2. **Build it behind a switch, off by default.** New behaviour arrives as an environment flag, such as
   `AETHER_CORE_MCP` or `AETHER_CORE_STATE_VIEW`, so the stock agent is untouched.
3. **Test the mechanics offline.** Real shell and file effects with a scripted model, including a known-bad case
   the test must catch. No API cost.
4. **Answer from existing logs if possible.** Many questions are settled for $0 by measuring hundreds of past
   runs before building anything.
5. **Run a small screen on real tasks.** 8 to 10 tasks, the switch on against off, typically a dollar or two.
6. **Confirm on different tasks.** A gain has to hold on a separate holdout set before it becomes the default.
7. **Decide.** Turn it on by default, keep it as an option, or remove it. The result is recorded either way.

## Three real examples

**Kept: stable facts.** Cost per run was higher than expected. The logs showed why: one block near the top of
every request changed each turn, so the provider re-read the whole history instead of using its cache. The fix
wrote changes as new entries instead. On the screen, cost fell to 0.52x with the same passes, and on a separate
holdout set to 0.76x. It became the default (commit `299be48`).

**Not built: a code map.** Other agents add a map of the codebase so the model finds things faster. Before
building one, a $0 scan of 289 real runs measured how much time goes on finding and reading files: 15% of steps,
5% of output. A map could save 5–10% at most, and maps add reasoning on these models. Decision: not built, with no
spend on runs.

**Fixed: a hang that froze everything after it.** In testing, one tool server died and every later call
waited out its full timeout. The fix checks that the server is alive while waiting and recovers the requests it
never answered. It shipped with Linux end-to-end tests that fail without it.

## Guardrails

- **Every module stays under 500 lines,** so each part can be read in one sitting.
- **No fake greens.** A test that a known-bad case cannot fail is not a test, and a pass built on mocks or stubs
  does not count.
- **The model owns the task.** Core gives it facts and tools; it never decides what the task means.
- **Everything is recorded,** so any claim can be checked against the run that produced it.
