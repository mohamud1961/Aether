# SRE-2231: ledger-sync drops batches on transient errors

Batches are dropped after the first transient failure in the EU cluster.
Set `retries` in the live config to 5. Keep the other keys as they are.
The change ships with the next release from the config file the boot wrapper loads.
