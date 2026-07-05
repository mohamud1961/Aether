# EnvMap Audit Report

Deterministic audit only: no models, no Docker, no grader, no verifier.

- Indexed tasks audited: 90
- Truncated file trees: 0
- Tasks with environment directories: 90
- Tasks with visible tests/checkers: 7
- Tasks with tooling hints in instructions: 54

## Top Tool Hints

- `python`: 20
- `make`: 16
- `r`: 7
- `gcc`: 5
- `node`: 4
- `git`: 4
- `nginx`: 3
- `qemu`: 3
- `expect`: 3
- `python3`: 3
- `g++`: 2
- `ssh`: 2
- `curl`: 1
- `openssl`: 1

## Risk Flags

- `sparse_visible_workspace`: 59
- `deliverable_pressure_with_few_input_hints`: 58
- `heavy_visible_test_surface`: 1

## Task Board

| task | files | tests | env dir | tool hints | output paths | risk flags |
|---|---:|---:|---|---|---|---|
| adaptive-rejection-sampler | 2 | 0 | yes | r | /app/ars.R, /app/normal_samples.txt, /app/exponential_samples.txt | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| bn-fit-modify | 1 | 0 | yes | node | /app/bn_sample_10k.csv, /app/learned_dag.csv, /app/intervened_dag.csv, /app/final_bn_sample.csv | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| break-filter-js-from-html | 4 | 2 | yes | python | /app/filter.py, /app/out.html, /app/test_outputs.py | deliverable_pressure_with_few_input_hints |
| build-cython-ext | 1 | 0 | yes | python, git, make | /app/pyknotid, /app/pyknotid/tests/test_random_curves.py, /app/pyknotid/tests/test_catalogue.py | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| build-pmars | 3 | 0 | yes | r | none | none |
| build-pov-ray | 2 | 0 | yes | none | /app/povray-2.2, /app/deps/illum1.pov, /app/povray-2.2/povdoc/include | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| caffe-cifar-10 | 1 | 0 | yes | none | /app/caffe, /app/caffe/training_output.txt | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| cancel-async-tasks | 1 | 0 | yes | python | /app/run.py | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| chess-best-move | 2 | 0 | yes | none | /app/move.txt | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| circuit-fibsqrt | 4 | 2 | yes | none | /app/sim.c, /app/gates.txt, /app/sim | deliverable_pressure_with_few_input_hints |
| cobol-modernization | 6 | 0 | yes | python | /app/src/program.cbl, /app/src/INPUT.DAT, /app/data/, /app/program.py, /app/data/ACCOUNTS.DAT, /app/data/BOOKS.DAT, /app/data/TRANSACTIONS.DAT | none |
| code-from-image | 2 | 0 | yes | make | /app/code.png, /app/output.txt | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| compile-compcert | 1 | 0 | yes | none | none | sparse_visible_workspace |
| configure-git-webserver | 1 | 0 | yes | git, curl | none | sparse_visible_workspace |
| constraints-scheduling | 4 | 0 | yes | none | /app/alice_calendar.ics, /app/bob_calendar.ics, /app/carol_calendar.ics, /app/meeting_scheduled.ics | none |
| count-dataset-tokens | 1 | 0 | yes | none | /app/answer.txt | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| crack-7z-hash | 2 | 0 | yes | none | /app/solution.txt | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| custom-memory-heap-crash | 6 | 0 | yes | gcc, g++ | /app/user.cpp, /app/release, /app/main.cpp, /app/debug | deliverable_pressure_with_few_input_hints |
| db-wal-recovery | 5 | 0 | yes | none | /app/, /app/recovered.json | deliverable_pressure_with_few_input_hints |
| distribution-search | 1 | 0 | yes | python | /app/dist.npy | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| dna-assembly | 2 | 0 | yes | make | none | sparse_visible_workspace |
| dna-insert | 2 | 0 | yes | none | none | sparse_visible_workspace |
| execution-gate-toy | 0 | 0 | yes | none | none | sparse_visible_workspace |
| extract-elf | 2 | 0 | yes | node | /app/a.out | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| extract-moves-from-video | 1 | 0 | yes | none | /app/solution.txt | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| feal-differential-cryptanalysis | 2 | 0 | yes | make | /app/feal.py, /app/attack.py | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| feal-linear-cryptanalysis | 4 | 0 | yes | make | /app/feal.c, /app/decrypt.c, /app/pairs.txt, /app/ciphertexts.txt, /app/plaintexts.txt | deliverable_pressure_with_few_input_hints |
| filter-js-from-html | 1 | 0 | yes | python | /app/filter.py | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| financial-document-processor | 19 | 0 | yes | none | /app/documents/, /app/invoices/, /app/other/, /app/invoices/summary.csv | deliverable_pressure_with_few_input_hints |
| fix-code-vulnerability | 1 | 0 | yes | python, make | /app/bottle.py, /app/report.jsonl, /app/example.cpp | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| fix-git | 4 | 0 | yes | none | none | none |
| fix-ocaml-gc | 1 | 0 | yes | make | none | sparse_visible_workspace |
| gcode-to-text | 2 | 0 | yes | none | /app/out.txt | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| git-leak-recovery | 2 | 0 | yes | make | /app/secret.txt, /app/repo | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| git-multibranch | 2 | 0 | yes | git, ssh, nginx | none | sparse_visible_workspace |
| gpt2-codegolf | 2 | 0 | yes | gcc | /app/gpt2.c, /app/a.out | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| headless-terminal | 2 | 0 | yes | python, make | /app/headless_terminal.py | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| hf-model-inference | 1 | 0 | yes | python | /app/model_cache/sentiment_model | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| install-windows-3.11 | 9 | 0 | yes | nginx, qemu | /app/isos/win311.img | deliverable_pressure_with_few_input_hints |
| kv-store-grpc | 1 | 0 | yes | python | /app/kv-store.proto, /app/server.py | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| large-scale-text-editing | 4 | 2 | yes | none | /app/input.csv, /app/expected.csv, /app/apply_macros.vim | deliverable_pressure_with_few_input_hints |
| largest-eigenval | 3 | 0 | yes | python | /app/eigen.py, /app/eval.py | deliverable_pressure_with_few_input_hints |
| llm-inference-batching-scheduler | 6 | 0 | yes | r | /app/task_file/input_data/requests_bucket_1.jsonl, /app/task_file/input_data/requests_bucket_2.jsonl, /app/task_file/output_data/plan_b1.jsonl, /app/task_file/output_data/plan_b2.jsonl, /app/task_file/scripts/cost_model.py, /app/task_file/scripts/baseline_packer.py | none |
| log-summary-date-ranges | 2 | 0 | yes | none | /app/logs, /app/summary.csv | sparse_visible_workspace |
| mailman | 2 | 0 | yes | none | /app/eval.py | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| make-doom-for-mips | 3 | 0 | yes | node, expect | /app/doomgeneric/ | deliverable_pressure_with_few_input_hints |
| make-mips-interpreter | 2 | 0 | yes | node | /app/doomgeneric_mips | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| mcmc-sampling-stan | 2 | 0 | yes | r | /app/data.csv, /app/analysis.R, /app/posterior_alpha_mean.txt, /app/posterior_beta_mean.txt, /app/hierarchical_model.stan | sparse_visible_workspace |
| merge-diff-arc-agi-task | 4 | 0 | yes | git | /app/repo, /app/bundle1.bundle, /app/bundle2.bundle, /app/repo/algo.py, /app/examples.json | deliverable_pressure_with_few_input_hints |
| model-extraction-relu-logits | 2 | 0 | yes | none | /app/steal.py, /app/stolen_A1.npy | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| modernize-scientific-stack | 6 | 0 | yes | python | /app/climate_analyzer/analyze_climate.py, /app/analyze_climate_modern.py, /app/requirements.txt, /app/pyproject.toml, /app/climate_analyzer/sample_data/climate_data.csv, /app/climate_analyzer/config.ini | none |
| mteb-leaderboard | 1 | 0 | yes | none | /app/result.txt | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| mteb-retrieve | 2 | 0 | yes | none | /app/data.txt, /app/result.txt | sparse_visible_workspace |
| multi-source-data-merger | 4 | 0 | yes | none | /app/merged_users.parquet, /app/conflicts.json | none |
| nginx-request-logging | 1 | 0 | yes | nginx | none | sparse_visible_workspace |
| openssl-selfsigned-cert | 1 | 0 | yes | python, openssl | /app/ssl/, /app/ssl/server.key, /app/ssl/server.crt, /app/ssl/server.pem, /app/ssl/verification.txt, /app/check_cert.py | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| overfull-hbox | 5 | 4 | yes | make | none | none |
| password-recovery | 2 | 0 | yes | make | /app/recovered_passwords.txt | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| path-tracing | 2 | 0 | yes | gcc, expect | /app/image.ppm | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| path-tracing-reverse | 2 | 0 | yes | gcc | /app/mystery, /app/mystery.c | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| polyglot-c-py | 1 | 0 | yes | python3, gcc | /app/polyglot/main.py.c, /app/polyglot/cmain | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| polyglot-rust-c | 1 | 0 | yes | g++ | /app/polyglot/main.rs, /app/polyglot/main, /app/polyglot/cmain | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| portfolio-optimization | 7 | 0 | yes | python, python3, r | none | none |
| protein-assembly | 5 | 0 | yes | make | /app/gblock.txt, /app/pdb_ids.txt | deliverable_pressure_with_few_input_hints |
| prove-plus-comm | 2 | 0 | yes | none | none | sparse_visible_workspace |
| pypi-server | 1 | 0 | yes | python | none | sparse_visible_workspace |
| pytorch-model-cli | 8 | 0 | yes | none | none | none |
| pytorch-model-recovery | 3 | 0 | yes | none | /app/weights.pt, /app/dataset.pt, /app/model.pt | none |
| qemu-alpine-ssh | 1 | 0 | yes | ssh, qemu | /app/alpine.iso | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| qemu-startup | 1 | 0 | yes | qemu, expect | /app/alpine.iso | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| query-optimize | 2 | 0 | yes | make | /app/oewn.sqlite, /app/my-sql-query.sql, /app/sol.sql | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| raman-fitting | 2 | 0 | yes | none | /app/results.json | sparse_visible_workspace |
| regex-chess | 2 | 1 | yes | python, make | /app/re.json | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| regex-log | 1 | 0 | yes | python | /app/regex.txt | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| reshard-c4-data | 3 | 0 | yes | python | /app/compress.py, /app/decompress.py | deliverable_pressure_with_few_input_hints |
| rstan-to-pystan | 6 | 1 | yes | python, r, make | /app/train_X.csv, /app/train_y.csv, /app/test_X.csv, /app/meta_public.json, /app/gp_rstan.R, /app/pystan_analysis.py, /app/alpha_est.csv, /app/sigma_est.csv, /app/rho_est.csv, /app/beta_est.csv | deliverable_pressure_with_few_input_hints |
| sam-cell-seg | 3 | 0 | yes | python | /app/demo_rgb.png, /app/demo_metadata.csv | none |
| sanitize-git-repo | 2 | 0 | yes | none | none | sparse_visible_workspace |
| schemelike-metacircular-eval | 67 | 25 | yes | python3 | none | heavy_visible_test_surface |
| sparql-university | 2 | 0 | yes | none | /app/university_graph.ttl, /app/solution.sparql | sparse_visible_workspace |
| sqlite-db-truncate | 2 | 0 | yes | none | /app/trunc.db, /app/recover.json | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| sqlite-with-gcov | 3 | 0 | yes | make | /app/sqlite, /app/vendor/sqlite-fossil-release.tar.gz | deliverable_pressure_with_few_input_hints |
| torch-pipeline-parallelism | 1 | 0 | yes | none | /app/pipeline_parallel.py | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| torch-tensor-parallelism | 1 | 0 | yes | none | /app/parallel_linear.py | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| train-fasttext | 2 | 0 | yes | none | /app/model.bin | sparse_visible_workspace |
| tune-mjcf | 3 | 0 | yes | none | /app/model_ref.xml, /app/model.xml, /app/eval.py | deliverable_pressure_with_few_input_hints |
| video-processing | 2 | 0 | yes | none | /app/jump_analyzer.py, /app/example_video.mp4, /app/output.toml | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| vulnerable-secret | 2 | 0 | yes | none | /app/results.txt | sparse_visible_workspace, deliverable_pressure_with_few_input_hints |
| winning-avg-corewars | 6 | 0 | yes | r | none | none |
| write-compressor | 4 | 0 | yes | none | /app/decomp.c, /app/data.txt, /app/decomp | none |
