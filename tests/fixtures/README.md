# iperf3 parser fixtures

Generated locally on 24 September 2026 using iperf3 3.18 in the project's Debian 13 amd64 development VM. The server bound only to `127.0.0.1`, on an ephemeral test port. Each client ran for two seconds with `-b 2M -J`; the reverse sample added `-R`. The temporary server was terminated after collection.

These are reduced real client outputs: only version, connection target, test settings and aggregate sender/receiver summaries are retained. They contain no RF measurements. The normal sample's `sum_received.sender` is true, while the reverse sample's is false: this flag identifies the reporting endpoint's role and must not be used to reject normal receiver metrics.

Original local capture: `vm/runtime/rf-parser-smoke.json` (ignored runtime evidence). Reduced fixtures preserve numeric values unchanged.
