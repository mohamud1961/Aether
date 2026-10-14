"""Inspect task factory with hidden host-side grading and candidate workspace-only files.

Importing/loading can be tested without a model. Docker execution qualification
is a separate gate. Entire final files and modes are copied back, including deletions.
"""

import base64
import json
import tempfile
from pathlib import Path

from .grading import grade
from .task import discover

FINAL_TREE = r"""
import json,os,stat
files=[]
for root,dirs,names in os.walk('.'):
    for name in dirs+names:
        p=os.path.join(root,name)
        if os.path.islink(p):raise ValueError('symlink final states are unsupported')
    for name in names:
        p=os.path.join(root,name);s=os.stat(p)
        if not stat.S_ISREG(s.st_mode):raise ValueError('non-regular final file')
        files.append({'path':p,'size':s.st_size,'mode':stat.S_IMODE(s.st_mode)})
if len(files)>512 or sum(f['size'] for f in files)>16777216:raise ValueError('inspection limit')
print(json.dumps(files))
"""


def make_task(tasks_root):
    from inspect_ai import Task
    from inspect_ai.dataset import Sample
    from inspect_ai.scorer import Score, accuracy, scorer
    from inspect_ai.solver import generate, use_tools
    from inspect_ai.tool import bash
    from inspect_ai.util import sandbox

    tasks = {t.id: t for t in discover(Path(tasks_root))}
    samples = []
    for t in tasks.values():
        files = {
            str(p.relative_to(t.workspace_dir)): "data:application/octet-stream;base64,"
            + base64.b64encode(p.read_bytes()).decode()
            for p in t.workspace_dir.rglob("*")
            if p.is_file()
        }
        samples.append(Sample(id=t.id, input=t.prompt, files=files))

    @scorer(metrics=[accuracy()])
    def state_grade():
        async def score(state, target):
            task = tasks[str(state.sample_id)]
            listed = await sandbox().exec(["python3", "-c", FINAL_TREE], timeout=30)
            if not listed.success:
                return Score(
                    value=0,
                    explanation="invalid inspection: unsupported final state; "
                    + listed.stderr,
                    metadata={"valid": False, "invalid_reason": "snapshot_error"},
                )
            with tempfile.TemporaryDirectory(prefix="inspect-final-") as temp:
                root = Path(temp).resolve()
                for item in json.loads(listed.stdout):
                    path = (root / item["path"]).resolve()
                    if not path.is_relative_to(root):
                        raise ValueError("unsafe final path")
                    path.parent.mkdir(parents=True, exist_ok=True)
                    content = await sandbox().read_file(item["path"], text=False)
                    path.write_bytes(content)
                    path.chmod(item["mode"])
                result = grade(task, root)
            return Score(
                value=int(result.passed),
                explanation=json.dumps(list(result.reasons)),
                metadata={"valid": result.error is None, "grader_error": result.error},
            )

        return score

    return Task(
        dataset=samples,
        solver=[use_tools([bash(timeout=180)]), generate()],
        scorer=state_grade(),
        sandbox="docker",
        message_limit=40,
    )
