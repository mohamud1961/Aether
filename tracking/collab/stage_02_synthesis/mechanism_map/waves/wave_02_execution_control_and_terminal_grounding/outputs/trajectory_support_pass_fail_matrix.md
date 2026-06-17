# Trajectory Support Pass/Fail Matrix

| task | system | run id | txt? | archive? | final outcome | visible divergence note |
| --- | --- | --- | --- | --- | --- | --- |
| break-filter-js-from-html | BigAI | `4389d2e9-7d17-4dc1-b0bd-5d1bde2716b6` | yes | yes | pass | 1/1 tests; readable run already passes |
| break-filter-js-from-html | BigAI | `4e6a3070-4a78-4c1a-ac1c-c0651045db08` | yes | yes | pass | 1/1 tests; readable run already passes |
| break-filter-js-from-html | BigAI | `6e8cb0c4-fcb1-4310-8f49-fd6505a405bd` | no | yes | pass | archive-only extra run; 1/1 tests |
| break-filter-js-from-html | BigAI | `76b82a2e-50bd-409b-97cf-1e244809da1b` | no | yes | pass | archive-only extra run; 1/1 tests |
| cancel-async-tasks | BigAI | `17f3a357-c55a-4171-af6a-510581362baa` | yes | yes | pass | 6/6 tests; one of the readable pass cases |
| cancel-async-tasks | BigAI | `71ef0a56-0b53-4639-974a-0190139c059c` | no | yes | pass | archive-only extra run; 6/6 tests |
| cancel-async-tasks | BigAI | `98b7cac5-17d9-401f-83aa-d65c59f4cdee` | yes | yes | fail | visible divergence: 5/6 tests; this is the only selected BigAI failure in the family |
| cancel-async-tasks | BigAI | `d7992f9a-d71d-4513-b06d-2d0a38757603` | yes | yes | pass | 6/6 tests; readable run already passes |
| db-wal-recovery | BigAI | `47f2454e-2528-4427-94c8-6b13f8c63f53` | yes | yes | pass | 7/7 tests; readable run already passes |
| db-wal-recovery | BigAI | `8586f6b0-3d1c-4eee-86b8-eee44cfad6c5` | no | yes | pass | archive-only extra run; 7/7 tests |
| db-wal-recovery | BigAI | `a1ed78b8-5ec9-4fb3-8a5a-e881a75c3bec` | yes | yes | pass | 7/7 tests; readable run already passes |
| db-wal-recovery | BigAI | `aea97873-3af7-4954-8c4f-a32b01b7cc99` | no | yes | pass | archive-only extra run; 7/7 tests |
| db-wal-recovery | BigAI | `e150eebe-6edd-4306-9d61-0b60351e4fa0` | yes | yes | pass | 7/7 tests; readable run already passes |
| git-multibranch | BigAI | `4faa9840-b48b-4bf0-a37d-303de24a0ac3` | no | yes | pass | archive-only extra run; 1/1 tests |
| git-multibranch | BigAI | `62d2bdf3-6678-44a2-bb90-efd397b7937d` | yes | yes | pass | 1/1 tests; readable run already passes |
| git-multibranch | BigAI | `64b05d98-c740-48e3-b46b-378a858786ba` | no | yes | pass | archive-only extra run; 1/1 tests |
| git-multibranch | BigAI | `baabd142-9b5e-457d-8c39-2cdf5bd4f462` | yes | yes | pass | 1/1 tests; readable run already passes |
| git-multibranch | BigAI | `bfcf2260-b5c7-4fa4-9662-5da094854b87` | no | yes | pass | archive-only extra run; 1/1 tests |
| headless-terminal | BigAI | `955f47f3-f86f-4989-a975-1299ed63a173` | no | yes | pass | archive-only extra run; 7/7 tests |
| headless-terminal | BigAI | `b579b8e9-66a0-4d35-8e21-4333c7db1146` | no | yes | pass | archive-only extra run; 7/7 tests |
| headless-terminal | BigAI | `c4676385-d244-44f5-ae16-7bccd71bbc7c` | no | yes | pass | archive-only extra run; 7/7 tests |
| headless-terminal | BigAI | `cec71502-c287-4257-9aba-4e33b3668881` | yes | yes | pass | 7/7 tests; readable run already passes |
| break-filter-js-from-html | deepagents | `802e3807-8f1a-4c15-991c-9cdb03d16cef` | yes | yes | fail | visible divergence: 0/1 tests |
| cancel-async-tasks | deepagents | `ca5a6b83-cd19-46da-8a12-1070b4f476bf` | yes | yes | fail | visible divergence: 5/6 tests |
| db-wal-recovery | deepagents | `0333a30b-2678-4f0e-a672-26279fd01b7a` | yes | yes | pass | 7/7 tests |
| git-multibranch | deepagents | `e6e6d3a5-ee75-489a-a4a0-c3a751ea3421` | yes | yes | pass | 1/1 tests |
| headless-terminal | deepagents | `8359bd4b-bdf5-4c33-b511-869e048e9f6f` | yes | yes | pass | 7/7 tests |
| break-filter-js-from-html | terminus-kira | `eaf5da17-d140-4652-bd00-3e6a83bf66cf` | yes | yes | pass | 1/1 tests |
| cancel-async-tasks | terminus-kira | `8d55545f-8ce2-49b7-9fc1-231635fc6a2d` | yes | yes | pass | 6/6 tests |
| db-wal-recovery | terminus-kira | `3481ab1c-d322-4bda-bd10-49c0708403d2` | yes | yes | fail | visible divergence: reward `0`; archive lacked `ctrf.json` in this scrape |
| git-multibranch | terminus-kira | `80b5619c-2b60-45e3-b209-ffbf02d27aa9` | yes | yes | pass | 1/1 tests |
| headless-terminal | terminus-kira | `a2ae3f53-cc59-4049-87ca-9e23781c00e4` | yes | yes | pass | 7/7 tests |

## Support notes

- The only selected-family failure contrasts in this support pass are:
  - `deepagents/break-filter-js-from-html/802e3807-8f1a-4c15-991c-9cdb03d16cef`
  - `deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf`
  - `terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2`
  - `BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee`
- All archive-only BigAI variants inspected in this support pass still ended in pass outcomes, so they increase coverage without changing the pass/fail split.
