# Server validation

The stock product runs on the dedicated Oregon AWS m6a.large test host:
2 vCPU, 8 GiB RAM, CPU-only inference, installed Ariadne Mark 0.4.0a0 wheel.
Three separate containers implement the product API/UI, persistent worker and
verifier. No SDK source is mounted over the installed package.

The [acceptance report](results/server-acceptance.json) records **39 passing
checks** against the running HTTP product. Each of six stock images and three
five-second 720p videos completed export, independent verification, checksum-
validated download and profile-receipt validation.

Additional checks cover duplicate submissions, conflicting idempotency keys,
arbitrary-path rejection, video byte ranges, corrupt input, visible disclosure,
a worker killed during video inference, recovery after restart, web/verifier
restarts, an unmarked negative control, and source-record recovery after a
marked image was re-encoded without C2PA metadata.

The first integration run exposed a service-readiness race: the product could
accept a verification request before the independent verifier was listening.
Compose now waits for verifier health before starting the web service. SQLite
connections in the product are explicitly closed after every operation. A
[1,000-read check](results/database-connections.json) with garbage collection
disabled held the process at four open file descriptors throughout.

The results establish this bounded integration workflow. The sample is not
representative enough for a production capacity or adversarial durability claim.
Stock stands in for a generator; fixture labelling and development issuer trust
are explicit. Worker-loss tests cover process/container interruption, not host
power loss or distributed object-storage semantics.
