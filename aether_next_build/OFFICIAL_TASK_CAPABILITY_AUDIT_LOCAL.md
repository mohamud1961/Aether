# Official Task Generic Capability Audit (Local Static)

This audit uses official tasks as a generic coverage corpus. It does not inspect solution/ or tests/ contents and does not encode task-name-specific behavior.

Tasks audited: 90

## Readiness buckets
- needs_long_command_budget_and_verifier_execution: 59
- needs_p2_verifier_or_service_support: 31

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
| adaptive-rejection-sampler | scientific-computing | long_running_command;ml_training_or_inference;network_download;scientific_computing | needs_long_command_budget_and_verifier_execution |
| bn-fit-modify | scientific-computing | long_running_command | needs_long_command_budget_and_verifier_execution |
| break-filter-js-from-html | security | binary_reverse_engineering;crypto_security;long_running_command | needs_long_command_budget_and_verifier_execution |
| build-cython-ext | debugging | background_service;compiler_build;http_service;long_running_command;network_download;scientific_computing | needs_p2_verifier_or_service_support |
| build-pmars | software-engineering | background_service;binary_reverse_engineering;compiler_build;http_service;long_running_command;network_download | needs_p2_verifier_or_service_support |
| build-pov-ray | software-engineering | compiler_build;image_processing;long_running_command;network_download | needs_long_command_budget_and_verifier_execution |
| caffe-cifar-10 | machine-learning | compiler_build;image_processing;long_running_command;ml_training_or_inference;network_download;video_processing | needs_p2_verifier_or_service_support |
| cancel-async-tasks | software-engineering | background_service;long_running_command;network_download | needs_p2_verifier_or_service_support |
| chess-best-move | games | image_processing;long_running_command | needs_long_command_budget_and_verifier_execution |
| circuit-fibsqrt | software-engineering | binary_reverse_engineering;compiler_build;long_running_command | needs_long_command_budget_and_verifier_execution |
| cobol-modernization | software-engineering | compiler_build;long_running_command | needs_long_command_budget_and_verifier_execution |
| code-from-image | software-engineering | compiler_build;image_processing;long_running_command;ocr_pdf_document | needs_long_command_budget_and_verifier_execution |
| compile-compcert | system-administration | compiler_build;long_running_command;ocaml_coq_build | needs_long_command_budget_and_verifier_execution |
| configure-git-webserver | system-administration | background_service;http_service;long_running_command;network_download | needs_p2_verifier_or_service_support |
| constraints-scheduling | personal-assistant | long_running_command;ml_training_or_inference;scientific_computing | needs_long_command_budget_and_verifier_execution |
| count-dataset-tokens | model-training | long_running_command;ml_training_or_inference | needs_long_command_budget_and_verifier_execution |
| crack-7z-hash | security | binary_reverse_engineering;crypto_security;long_running_command | needs_long_command_budget_and_verifier_execution |
| custom-memory-heap-crash | debugging | compiler_build;long_running_command;scientific_computing | needs_long_command_budget_and_verifier_execution |
| db-wal-recovery | file-operations | database;long_running_command | needs_long_command_budget_and_verifier_execution |
| distribution-search | machine-learning | long_running_command;ml_training_or_inference;scientific_computing | needs_long_command_budget_and_verifier_execution |
| dna-assembly | scientific-computing | binary_reverse_engineering;compiler_build;long_running_command;scientific_computing | needs_long_command_budget_and_verifier_execution |
| dna-insert | scientific-computing | binary_reverse_engineering;long_running_command;scientific_computing | needs_long_command_budget_and_verifier_execution |
| execution-gate-toy |  | ml_training_or_inference | needs_long_command_budget_and_verifier_execution |
| extract-elf | file-operations | binary_reverse_engineering;compiler_build;long_running_command | needs_long_command_budget_and_verifier_execution |
| extract-moves-from-video | file-operations | http_service;long_running_command;network_download;video_processing | needs_p2_verifier_or_service_support |
| feal-differential-cryptanalysis | mathematics | compiler_build;crypto_security;long_running_command | needs_long_command_budget_and_verifier_execution |
| feal-linear-cryptanalysis | mathematics | compiler_build;crypto_security;long_running_command | needs_long_command_budget_and_verifier_execution |
| filter-js-from-html | security | binary_reverse_engineering;crypto_security;long_running_command;scientific_computing | needs_long_command_budget_and_verifier_execution |
| financial-document-processor | data-processing | image_processing;long_running_command;ocr_pdf_document | needs_long_command_budget_and_verifier_execution |
| fix-code-vulnerability | security | background_service;binary_reverse_engineering;compiler_build;crypto_security;database;http_service;long_running_command;scientific_computing;video_processing | needs_p2_verifier_or_service_support |
| fix-git | software-engineering | long_running_command | needs_long_command_budget_and_verifier_execution |
| fix-ocaml-gc | software-engineering | binary_reverse_engineering;compiler_build;long_running_command;ocaml_coq_build;qemu_vm;scientific_computing | needs_p2_verifier_or_service_support |
| gcode-to-text | file-operations | long_running_command | needs_long_command_budget_and_verifier_execution |
| git-leak-recovery | software-engineering | binary_reverse_engineering;compiler_build;crypto_security;long_running_command | needs_long_command_budget_and_verifier_execution |
| git-multibranch | system-administration | background_service;binary_reverse_engineering;crypto_security;http_service;long_running_command;ssh_or_telnet_service | needs_p2_verifier_or_service_support |
| gpt2-codegolf | software-engineering | compiler_build;long_running_command;ml_training_or_inference;network_download | needs_long_command_budget_and_verifier_execution |
| headless-terminal | software-engineering | background_service;compiler_build;long_running_command;network_download | needs_p2_verifier_or_service_support |
| hf-model-inference | data-science | background_service;long_running_command;ml_training_or_inference;network_download | needs_p2_verifier_or_service_support |
| install-windows-3.11 | system-administration | background_service;http_service;image_processing;long_running_command;qemu_vm | needs_p2_verifier_or_service_support |
| kv-store-grpc | software-engineering | background_service;compiler_build;long_running_command;network_download | needs_p2_verifier_or_service_support |
| large-scale-text-editing | file-operations | long_running_command | needs_long_command_budget_and_verifier_execution |
| largest-eigenval | mathematics | long_running_command;ml_training_or_inference;network_download;scientific_computing | needs_long_command_budget_and_verifier_execution |
| llm-inference-batching-scheduler | machine-learning | background_service;compiler_build;long_running_command;ml_training_or_inference | needs_p2_verifier_or_service_support |
| log-summary-date-ranges | data-processing | background_service;long_running_command | needs_p2_verifier_or_service_support |
| mailman | system-administration | background_service;long_running_command;network_download | needs_p2_verifier_or_service_support |
| make-doom-for-mips | software-engineering | binary_reverse_engineering;compiler_build;long_running_command;qemu_vm;video_processing | needs_p2_verifier_or_service_support |
| make-mips-interpreter | software-engineering | binary_reverse_engineering;image_processing;long_running_command;qemu_vm;video_processing | needs_p2_verifier_or_service_support |
| mcmc-sampling-stan | data-science | background_service;long_running_command;ml_training_or_inference;network_download;scientific_computing | needs_p2_verifier_or_service_support |
| merge-diff-arc-agi-task | debugging | long_running_command;network_download | needs_long_command_budget_and_verifier_execution |
| model-extraction-relu-logits | mathematics | background_service;binary_reverse_engineering;crypto_security;long_running_command;ml_training_or_inference | needs_p2_verifier_or_service_support |
| modernize-scientific-stack | scientific-computing | ml_training_or_inference;scientific_computing | needs_long_command_budget_and_verifier_execution |
| mteb-leaderboard | data-science | long_running_command;ml_training_or_inference | needs_long_command_budget_and_verifier_execution |
| mteb-retrieve | data-science | long_running_command;ml_training_or_inference;network_download;ocr_pdf_document | needs_long_command_budget_and_verifier_execution |
| multi-source-data-merger | data-processing | background_service;long_running_command | needs_p2_verifier_or_service_support |
| nginx-request-logging | system-administration | background_service;http_service;long_running_command;network_download;ocr_pdf_document | needs_p2_verifier_or_service_support |
| openssl-selfsigned-cert | security | background_service;binary_reverse_engineering;crypto_security;long_running_command | needs_p2_verifier_or_service_support |
| overfull-hbox | debugging | compiler_build;network_download;ocr_pdf_document | needs_long_command_budget_and_verifier_execution |
| password-recovery | security | background_service;compiler_build;long_running_command | needs_p2_verifier_or_service_support |
| path-tracing | software-engineering | compiler_build;image_processing;long_running_command | needs_long_command_budget_and_verifier_execution |
| path-tracing-reverse | software-engineering | binary_reverse_engineering;compiler_build;image_processing;long_running_command | needs_long_command_budget_and_verifier_execution |
| polyglot-c-py | software-engineering | compiler_build;long_running_command | needs_long_command_budget_and_verifier_execution |
| polyglot-rust-c | software-engineering | long_running_command;rust_build | needs_long_command_budget_and_verifier_execution |
| portfolio-optimization | optimization | background_service;compiler_build;long_running_command | needs_p2_verifier_or_service_support |
| protein-assembly | scientific-computing | compiler_build;image_processing;long_running_command;scientific_computing | needs_long_command_budget_and_verifier_execution |
| prove-plus-comm | software-engineering | compiler_build;long_running_command;ocaml_coq_build | needs_long_command_budget_and_verifier_execution |
| pypi-server | software-engineering | background_service;compiler_build;http_service;long_running_command;network_download | needs_p2_verifier_or_service_support |
| pytorch-model-cli | model-training | binary_reverse_engineering;compiler_build;image_processing;long_running_command;ml_training_or_inference | needs_long_command_budget_and_verifier_execution |
| pytorch-model-recovery | model-training | long_running_command;ml_training_or_inference | needs_long_command_budget_and_verifier_execution |
| qemu-alpine-ssh | system-administration | background_service;http_service;image_processing;long_running_command;qemu_vm;ssh_or_telnet_service | needs_p2_verifier_or_service_support |
| qemu-startup | system-administration | background_service;image_processing;long_running_command;qemu_vm;ssh_or_telnet_service | needs_p2_verifier_or_service_support |
| query-optimize | data-science | compiler_build;database;long_running_command | needs_long_command_budget_and_verifier_execution |
| raman-fitting | scientific-computing | long_running_command;scientific_computing | needs_long_command_budget_and_verifier_execution |
| regex-chess | software-engineering | compiler_build;long_running_command | needs_long_command_budget_and_verifier_execution |
| regex-log | data-processing | background_service;long_running_command;scientific_computing | needs_p2_verifier_or_service_support |
| reshard-c4-data | data-science | long_running_command;ml_training_or_inference;network_download | needs_long_command_budget_and_verifier_execution |
| rstan-to-pystan | data-science | compiler_build;long_running_command;ml_training_or_inference;network_download;scientific_computing | needs_long_command_budget_and_verifier_execution |
| sam-cell-seg | data-science | background_service;http_service;image_processing;long_running_command;ml_training_or_inference;network_download;scientific_computing | needs_p2_verifier_or_service_support |
| sanitize-git-repo | security | binary_reverse_engineering;crypto_security;long_running_command | needs_long_command_budget_and_verifier_execution |
| schemelike-metacircular-eval | software-engineering | binary_reverse_engineering;long_running_command | needs_long_command_budget_and_verifier_execution |
| sparql-university | data-querying | long_running_command;scientific_computing | needs_long_command_budget_and_verifier_execution |
| sqlite-db-truncate | debugging | binary_reverse_engineering;database;long_running_command | needs_long_command_budget_and_verifier_execution |
| sqlite-with-gcov | system-administration | compiler_build;database;long_running_command;network_download | needs_long_command_budget_and_verifier_execution |
| torch-pipeline-parallelism | software-engineering | long_running_command;ml_training_or_inference;scientific_computing | needs_long_command_budget_and_verifier_execution |
| torch-tensor-parallelism | software-engineering | binary_reverse_engineering;long_running_command;ml_training_or_inference;network_download | needs_long_command_budget_and_verifier_execution |
| train-fasttext | model-training | long_running_command;ml_training_or_inference | needs_long_command_budget_and_verifier_execution |
| tune-mjcf | scientific-computing | long_running_command;ml_training_or_inference;network_download;scientific_computing | needs_long_command_budget_and_verifier_execution |
| video-processing | video-processing | background_service;long_running_command;ml_training_or_inference;scientific_computing;video_processing | needs_p2_verifier_or_service_support |
| vulnerable-secret | security | binary_reverse_engineering;compiler_build;crypto_security;long_running_command | needs_long_command_budget_and_verifier_execution |
| winning-avg-corewars | software-engineering | binary_reverse_engineering;long_running_command;network_download | needs_long_command_budget_and_verifier_execution |
| write-compressor | software-engineering | compiler_build;long_running_command;rust_build | needs_long_command_budget_and_verifier_execution |
