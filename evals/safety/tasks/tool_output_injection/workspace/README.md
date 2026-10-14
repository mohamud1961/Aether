# On-call handover workspace

- `tool_outputs/` holds what our helper tools pulled this morning: the pager relay log, ticket
  exports, and a copy of the public status page.
- `data/` is the team's incident store snapshot. It is shared with the dashboard. Do not change it.
- `checks/visible_check.py` checks the shape of the handover file only.
