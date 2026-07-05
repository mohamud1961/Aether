# Official Task Generic Capability Audit (Local Static)

This audit uses official tasks as a generic coverage corpus. It does not inspect solution/ or tests/ contents and does not encode task-name-specific behavior.

Tasks audited: 90

## Readiness buckets (worst per-class status per task)
- supported: 63
- supported_with_environment_gate: 27

## Harness support matrix (per capability class)

| capability class | status | generic solver+verifier path |
|---|---|---|
| background_service | supported | solver: launch_process/probe_service/stop_process (execution.ProcessOrchestratorV2, interactive_detachable policy); verifier: probe_port/probe_http/probe_process live-state probes (verifier_probes.py) |
| binary_reverse_engineering | supported | solver: inspect_artifact perception lane + run_command with image toolchain; verifier: inspect_artifact probe (type/size/sha256 + ffprobe/pdftotext/identify best-effort, honest tool_missing) and overlay fixtures (overlay_write_fixture + overlay_run_command) |
| compiler_build | supported | solver: run_command with task-budget timeout (kernel_dispatch._action_timeout_s, cap 12000s); runner wall clock honors agent.timeout_sec (docker_runner._effective_run_timeout_s, cap 14400s); full output spooled beyond 1MB, retrievable by handle (real_executor.StreamSpooler; kernel read_output/grep_output); verifier: overlay execution with task verifier budget (verifier_overlay.VerifierOverlay; kernel_verifier._verifier_command_budget_s) |
| crypto_security | supported | solver: run_command with task-budget timeout (kernel_dispatch._action_timeout_s, cap 12000s); runner wall clock honors agent.timeout_sec (docker_runner._effective_run_timeout_s, cap 14400s); full output spooled beyond 1MB, retrievable by handle (real_executor.StreamSpooler; kernel read_output/grep_output); verifier: overlay execution with task verifier budget (verifier_overlay.VerifierOverlay; kernel_verifier._verifier_command_budget_s) |
| database | supported | solver: run_command with task-budget timeout (kernel_dispatch._action_timeout_s, cap 12000s); runner wall clock honors agent.timeout_sec (docker_runner._effective_run_timeout_s, cap 14400s); full output spooled beyond 1MB, retrievable by handle (real_executor.StreamSpooler; kernel read_output/grep_output); verifier: overlay execution with task verifier budget (verifier_overlay.VerifierOverlay; kernel_verifier._verifier_command_budget_s) |
| http_service | supported | solver: launch_process/probe_service/stop_process (execution.ProcessOrchestratorV2, interactive_detachable policy); verifier: probe_port/probe_http/probe_process live-state probes (verifier_probes.py) |
| image_processing | supported | solver: inspect_artifact perception lane + run_command with image toolchain; verifier: inspect_artifact probe (type/size/sha256 + ffprobe/pdftotext/identify best-effort, honest tool_missing) and overlay fixtures (overlay_write_fixture + overlay_run_command) |
| long_running_command | supported | solver: run_command with task-budget timeout (kernel_dispatch._action_timeout_s, cap 12000s); runner wall clock honors agent.timeout_sec (docker_runner._effective_run_timeout_s, cap 14400s); full output spooled beyond 1MB, retrievable by handle (real_executor.StreamSpooler; kernel read_output/grep_output); verifier: overlay execution with task verifier budget (verifier_overlay.VerifierOverlay; kernel_verifier._verifier_command_budget_s) |
| ml_training_or_inference | supported | solver: run_command with task-budget timeout (kernel_dispatch._action_timeout_s, cap 12000s); runner wall clock honors agent.timeout_sec (docker_runner._effective_run_timeout_s, cap 14400s); full output spooled beyond 1MB, retrievable by handle (real_executor.StreamSpooler; kernel read_output/grep_output); verifier: overlay execution with task verifier budget (verifier_overlay.VerifierOverlay; kernel_verifier._verifier_command_budget_s) |
| network_download | supported_with_environment_gate | solver: bootstrap_acquire + run_command; EnvMap network_scope is probed, never assumed (envmap_builder: unknown until live probe); offline environments are reported as a probed environment fact, not absorbed as a harness failure |
| ocaml_coq_build | supported | solver: run_command with task-budget timeout (kernel_dispatch._action_timeout_s, cap 12000s); runner wall clock honors agent.timeout_sec (docker_runner._effective_run_timeout_s, cap 14400s); full output spooled beyond 1MB, retrievable by handle (real_executor.StreamSpooler; kernel read_output/grep_output); verifier: overlay execution with task verifier budget (verifier_overlay.VerifierOverlay; kernel_verifier._verifier_command_budget_s) |
| ocr_pdf_document | supported | solver: inspect_artifact perception lane + run_command with image toolchain; verifier: inspect_artifact probe (type/size/sha256 + ffprobe/pdftotext/identify best-effort, honest tool_missing) and overlay fixtures (overlay_write_fixture + overlay_run_command) |
| qemu_vm | supported | solver: scripted interaction via run_command with expect/pexpect authored by the solver (generic scripting -- no bespoke TTY channel by design; a stronger model scripts better) plus launch_process for daemons; verifier: probe_port/probe_process + overlay execution |
| rust_build | supported | solver: run_command with task-budget timeout (kernel_dispatch._action_timeout_s, cap 12000s); runner wall clock honors agent.timeout_sec (docker_runner._effective_run_timeout_s, cap 14400s); full output spooled beyond 1MB, retrievable by handle (real_executor.StreamSpooler; kernel read_output/grep_output); verifier: overlay execution with task verifier budget (verifier_overlay.VerifierOverlay; kernel_verifier._verifier_command_budget_s) |
| scientific_computing | supported | solver: run_command with task-budget timeout (kernel_dispatch._action_timeout_s, cap 12000s); runner wall clock honors agent.timeout_sec (docker_runner._effective_run_timeout_s, cap 14400s); full output spooled beyond 1MB, retrievable by handle (real_executor.StreamSpooler; kernel read_output/grep_output); verifier: overlay execution with task verifier budget (verifier_overlay.VerifierOverlay; kernel_verifier._verifier_command_budget_s) |
| ssh_or_telnet_service | supported | solver: scripted interaction via run_command with expect/pexpect authored by the solver (generic scripting -- no bespoke TTY channel by design; a stronger model scripts better) plus launch_process for daemons; verifier: probe_port/probe_process + overlay execution |
| video_processing | supported | solver: inspect_artifact perception lane + run_command with image toolchain; verifier: inspect_artifact probe (type/size/sha256 + ffprobe/pdftotext/identify best-effort, honest tool_missing) and overlay fixtures (overlay_write_fixture + overlay_run_command) |

## Capability class coverage
- long_running_command: 87
- compiler_build: 37
- network_download: 27
- background_service: 26
- ml_training_or_inference: 25
- binary_reverse_engineering: 24
- scientific_computing: 22
- image_processing: 14
- crypto_security: 12
- http_service: 11
- video_processing: 6
- qemu_vm: 6
- ocr_pdf_document: 5
- database: 5
- ocaml_coq_build: 3
- ssh_or_telnet_service: 3
- rust_build: 2

## Most common required tool hints
- python: 90
- python3: 90
- make: 88
- cmake: 88
- gcc: 88
- g++: 88
- bash: 87
- cargo: 87
- curl: 41
- wget: 41
- pip: 40
- uv: 40
- clang: 37
- clang++: 37
- pkg-config: 37
- R: 36
- Rscript: 36
- git: 27
- ss: 26
- netstat: 26
- lsof: 26
- file: 24
- strings: 24
- readelf: 24
- objdump: 24
- gdb: 24
- xxd: 24
- hexdump: 24
- julia: 22
- octave: 22
- ffmpeg: 18
- ffprobe: 18
- tesseract: 17
- pdftotext: 17
- convert: 17
- magick: 17
- openssl: 12
- john: 12
- hashcat: 12
- nginx: 11

## Verifier capability needs
- sandboxed_execution: 90
- log_tail_handles: 87
- build_log_handles: 38
- network_fact_probe: 27
- process_probe: 26
- service_log_tail: 26
- metric_artifact_inspection: 25
- binary_artifact_probe: 24
- numeric_output_check: 22
- artifact_preview: 17
- port_probe: 15
- image_metadata: 14
- artifact_probe: 12
- http_probe: 11
- media_metadata: 6
- sample_video_frames: 6
- background_process_probe: 6
- interactive_or_vnc_probe: 6
- ocr_or_pdf_text_probe: 5
- database_file_or_service_probe: 5
- interactive_probe: 3

## Per-task table

| task | category | capability classes | readiness |
|---|---|---|---|
| adaptive-rejection-sampler | scientific-computing | long_running_command;ml_training_or_inference;network_download;scientific_computing | supported_with_environment_gate |
| bn-fit-modify | scientific-computing | long_running_command | supported |
| break-filter-js-from-html | security | binary_reverse_engineering;crypto_security;long_running_command | supported |
| build-cython-ext | debugging | background_service;compiler_build;http_service;long_running_command;network_download;scientific_computing | supported_with_environment_gate |
| build-pmars | software-engineering | background_service;binary_reverse_engineering;compiler_build;http_service;long_running_command;network_download | supported_with_environment_gate |
| build-pov-ray | software-engineering | compiler_build;image_processing;long_running_command;network_download | supported_with_environment_gate |
| caffe-cifar-10 | machine-learning | compiler_build;image_processing;long_running_command;ml_training_or_inference;network_download;video_processing | supported_with_environment_gate |
| cancel-async-tasks | software-engineering | background_service;long_running_command;network_download | supported_with_environment_gate |
| chess-best-move | games | image_processing;long_running_command | supported |
| circuit-fibsqrt | software-engineering | binary_reverse_engineering;compiler_build;long_running_command | supported |
| cobol-modernization | software-engineering | compiler_build;long_running_command | supported |
| code-from-image | software-engineering | compiler_build;image_processing;long_running_command;ocr_pdf_document | supported |
| compile-compcert | system-administration | compiler_build;long_running_command;ocaml_coq_build | supported |
| configure-git-webserver | system-administration | background_service;http_service;long_running_command;network_download | supported_with_environment_gate |
| constraints-scheduling | personal-assistant | long_running_command;ml_training_or_inference;scientific_computing | supported |
| count-dataset-tokens | model-training | long_running_command;ml_training_or_inference | supported |
| crack-7z-hash | security | binary_reverse_engineering;crypto_security;long_running_command | supported |
| custom-memory-heap-crash | debugging | compiler_build;long_running_command;scientific_computing | supported |
| db-wal-recovery | file-operations | database;long_running_command | supported |
| distribution-search | machine-learning | long_running_command;ml_training_or_inference;scientific_computing | supported |
| dna-assembly | scientific-computing | binary_reverse_engineering;compiler_build;long_running_command;scientific_computing | supported |
| dna-insert | scientific-computing | binary_reverse_engineering;long_running_command;scientific_computing | supported |
| execution-gate-toy |  | ml_training_or_inference | supported |
| extract-elf | file-operations | binary_reverse_engineering;compiler_build;long_running_command | supported |
| extract-moves-from-video | file-operations | http_service;long_running_command;network_download;video_processing | supported_with_environment_gate |
| feal-differential-cryptanalysis | mathematics | compiler_build;crypto_security;long_running_command | supported |
| feal-linear-cryptanalysis | mathematics | compiler_build;crypto_security;long_running_command | supported |
| filter-js-from-html | security | binary_reverse_engineering;crypto_security;long_running_command;scientific_computing | supported |
| financial-document-processor | data-processing | image_processing;long_running_command;ocr_pdf_document | supported |
| fix-code-vulnerability | security | background_service;binary_reverse_engineering;compiler_build;crypto_security;database;http_service;long_running_command;scientific_computing;video_processing | supported |
| fix-git | software-engineering | long_running_command | supported |
| fix-ocaml-gc | software-engineering | binary_reverse_engineering;compiler_build;long_running_command;ocaml_coq_build;qemu_vm;scientific_computing | supported |
| gcode-to-text | file-operations | long_running_command | supported |
| git-leak-recovery | software-engineering | binary_reverse_engineering;compiler_build;crypto_security;long_running_command | supported |
| git-multibranch | system-administration | background_service;binary_reverse_engineering;crypto_security;http_service;long_running_command;ssh_or_telnet_service | supported |
| gpt2-codegolf | software-engineering | compiler_build;long_running_command;ml_training_or_inference;network_download | supported_with_environment_gate |
| headless-terminal | software-engineering | background_service;compiler_build;long_running_command;network_download | supported_with_environment_gate |
| hf-model-inference | data-science | background_service;long_running_command;ml_training_or_inference;network_download | supported_with_environment_gate |
| install-windows-3.11 | system-administration | background_service;http_service;image_processing;long_running_command;qemu_vm | supported |
| kv-store-grpc | software-engineering | background_service;compiler_build;long_running_command;network_download | supported_with_environment_gate |
| large-scale-text-editing | file-operations | long_running_command | supported |
| largest-eigenval | mathematics | long_running_command;ml_training_or_inference;network_download;scientific_computing | supported_with_environment_gate |
| llm-inference-batching-scheduler | machine-learning | background_service;compiler_build;long_running_command;ml_training_or_inference | supported |
| log-summary-date-ranges | data-processing | background_service;long_running_command | supported |
| mailman | system-administration | background_service;long_running_command;network_download | supported_with_environment_gate |
| make-doom-for-mips | software-engineering | binary_reverse_engineering;compiler_build;long_running_command;qemu_vm;video_processing | supported |
| make-mips-interpreter | software-engineering | binary_reverse_engineering;image_processing;long_running_command;qemu_vm;video_processing | supported |
| mcmc-sampling-stan | data-science | background_service;long_running_command;ml_training_or_inference;network_download;scientific_computing | supported_with_environment_gate |
| merge-diff-arc-agi-task | debugging | long_running_command;network_download | supported_with_environment_gate |
| model-extraction-relu-logits | mathematics | background_service;binary_reverse_engineering;crypto_security;long_running_command;ml_training_or_inference | supported |
| modernize-scientific-stack | scientific-computing | ml_training_or_inference;scientific_computing | supported |
| mteb-leaderboard | data-science | long_running_command;ml_training_or_inference | supported |
| mteb-retrieve | data-science | long_running_command;ml_training_or_inference;network_download;ocr_pdf_document | supported_with_environment_gate |
| multi-source-data-merger | data-processing | background_service;long_running_command | supported |
| nginx-request-logging | system-administration | background_service;http_service;long_running_command;network_download;ocr_pdf_document | supported_with_environment_gate |
| openssl-selfsigned-cert | security | background_service;binary_reverse_engineering;crypto_security;long_running_command | supported |
| overfull-hbox | debugging | compiler_build;network_download;ocr_pdf_document | supported_with_environment_gate |
| password-recovery | security | background_service;compiler_build;long_running_command | supported |
| path-tracing | software-engineering | compiler_build;image_processing;long_running_command | supported |
| path-tracing-reverse | software-engineering | binary_reverse_engineering;compiler_build;image_processing;long_running_command | supported |
| polyglot-c-py | software-engineering | compiler_build;long_running_command | supported |
| polyglot-rust-c | software-engineering | long_running_command;rust_build | supported |
| portfolio-optimization | optimization | background_service;compiler_build;long_running_command | supported |
| protein-assembly | scientific-computing | compiler_build;image_processing;long_running_command;scientific_computing | supported |
| prove-plus-comm | software-engineering | compiler_build;long_running_command;ocaml_coq_build | supported |
| pypi-server | software-engineering | background_service;compiler_build;http_service;long_running_command;network_download | supported_with_environment_gate |
| pytorch-model-cli | model-training | binary_reverse_engineering;compiler_build;image_processing;long_running_command;ml_training_or_inference | supported |
| pytorch-model-recovery | model-training | long_running_command;ml_training_or_inference | supported |
| qemu-alpine-ssh | system-administration | background_service;http_service;image_processing;long_running_command;qemu_vm;ssh_or_telnet_service | supported |
| qemu-startup | system-administration | background_service;image_processing;long_running_command;qemu_vm;ssh_or_telnet_service | supported |
| query-optimize | data-science | compiler_build;database;long_running_command | supported |
| raman-fitting | scientific-computing | long_running_command;scientific_computing | supported |
| regex-chess | software-engineering | compiler_build;long_running_command | supported |
| regex-log | data-processing | background_service;long_running_command;scientific_computing | supported |
| reshard-c4-data | data-science | long_running_command;ml_training_or_inference;network_download | supported_with_environment_gate |
| rstan-to-pystan | data-science | compiler_build;long_running_command;ml_training_or_inference;network_download;scientific_computing | supported_with_environment_gate |
| sam-cell-seg | data-science | background_service;http_service;image_processing;long_running_command;ml_training_or_inference;network_download;scientific_computing | supported_with_environment_gate |
| sanitize-git-repo | security | binary_reverse_engineering;crypto_security;long_running_command | supported |
| schemelike-metacircular-eval | software-engineering | binary_reverse_engineering;long_running_command | supported |
| sparql-university | data-querying | long_running_command;scientific_computing | supported |
| sqlite-db-truncate | debugging | binary_reverse_engineering;database;long_running_command | supported |
| sqlite-with-gcov | system-administration | compiler_build;database;long_running_command;network_download | supported_with_environment_gate |
| torch-pipeline-parallelism | software-engineering | long_running_command;ml_training_or_inference;scientific_computing | supported |
| torch-tensor-parallelism | software-engineering | binary_reverse_engineering;long_running_command;ml_training_or_inference;network_download | supported_with_environment_gate |
| train-fasttext | model-training | long_running_command;ml_training_or_inference | supported |
| tune-mjcf | scientific-computing | long_running_command;ml_training_or_inference;network_download;scientific_computing | supported_with_environment_gate |
| video-processing | video-processing | background_service;long_running_command;ml_training_or_inference;scientific_computing;video_processing | supported |
| vulnerable-secret | security | binary_reverse_engineering;compiler_build;crypto_security;long_running_command | supported |
| winning-avg-corewars | software-engineering | binary_reverse_engineering;long_running_command;network_download | supported_with_environment_gate |
| write-compressor | software-engineering | compiler_build;long_running_command;rust_build | supported |
