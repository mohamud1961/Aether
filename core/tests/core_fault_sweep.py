"""Every-exec fault injection for operation sweeps (real shells).

After ``armed`` is set, the environment numbers each container exec. In discovery mode (``target`` None) every exec
runs under a bash DEBUG trap that counts its simple commands, so a sweep learns how many kill points each exec has.
In fault mode the ``target``-th exec runs under a trap that exits before its ``cut``-th simple command (``cut`` past
the last command lets it finish), and its reply is then lost (ConnectionError). Every later exec runs normally.
So the sweep covers every point at which a controller can lose an operation's exec, whatever the protocol's shape.
"""

import shlex

from tests.core_fakes import LocalEnv


def _under_trap(command: str, counter: str, cut: int | None) -> str:
    stop = f'[ "$n" -ge {cut} ] && exit 99; ' if cut is not None else ""
    trap = f"n=$((n+1)); echo $n > {shlex.quote(counter)}; {stop}"
    return f"bash -c {shlex.quote('n=0; trap ' + shlex.quote(trap) + ' DEBUG; eval \"$1\"')} _ {shlex.quote(command)}"


class CutExecs(LocalEnv):
    def __init__(self, root, target: int | None = None, cut: int | None = None):
        super().__init__(root)
        self.target, self.cut = target, cut
        self.armed, self.fired, self.index = False, False, 0
        self.counts: list[int] = []

    async def exec(self, command, **kwargs):
        if not self.armed or self.fired:
            return await super().exec(command, **kwargs)
        i, self.index = self.index, self.index + 1
        counter = str(self.root / f".exec-{i}.n")
        if self.target is None:
            result = await super().exec(_under_trap(command, counter, None), **kwargs)
            with open(counter) as handle:
                self.counts.append(int(handle.read()))
            return result
        if i != self.target:
            return await super().exec(command, **kwargs)
        self.fired = True
        await super().exec(_under_trap(command, counter, self.cut), **kwargs)
        raise ConnectionError(f"the controller lost exec {i}")


def kill_points(counts: list[int]) -> list[tuple[int, int]]:
    """(exec, cut) for every simple command of every exec, plus each exec's lost reply."""
    return [(e, k) for e, n in enumerate(counts) for k in range(1, n + 2)]
