# Use Ariadne from Node.js, Next.js or a mobile backend

Ariadne Mark 0.7.2a1 is a Python/CLI media backend for Linux x86-64. It is not
an npm marking package or an on-device iOS/Android SDK. Your web/mobile product
submits a generation job; an owned backend worker marks the final file before
your normal object-store/CDN publication step.

## Connect to the existing export queue

1. Generate, crop, resize and encode the final supported rendition.
2. Resolve the job to server-owned paths, publisher/system/version and real creation time.
3. Export through a provisioned Python worker or a subprocess in a bounded job queue.
4. Check success and receipt, then publish the returned file. Surface failures as failed jobs.
5. Verify bytes downloaded through the actual CDN/app; repeat for every rendition.

Do not accept an arbitrary command/path from a browser or run a model download
inside a web request. For Next.js, enqueue from a server route and process outside
the request lifecycle. Short-lived edge/serverless execution is not the qualified
media environment. Provider signing/report keys and the registry stay off clients.

## Minimal CLI bridge

The following function assumes `ariadne` and its runtime are already installed
in the backend environment. Arguments and paths are derived from your own job
record, not passed through from an HTTP request. This example uses development
credentials for the downloadable sample; production configuration is separate.

```javascript
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
const exec = promisify(execFile);

export async function exportImage(job) {
  const args = ['mark', job.input, job.output,
    '--publisher', job.publisher, '--system', job.system,
    '--system-version', job.systemVersion, '--created-at', job.createdAt,
    '--identity', job.identity, '--allow-dev', '--registry', job.registry];
  const { stdout } = await exec('ariadne', args, {
    shell: false, timeout: 300_000, maxBuffer: 2 * 1024 * 1024,
    env: process.env,
  });
  return JSON.parse(stdout);
}
```

Non-zero exit or timeout rejects the job. A timeout is not proof that a child
process tree has stopped: use container/job-level cancellation and reconcile
staging outputs before retry. A batch may contain earlier successful exports.
The subprocess form starts a new runtime per invocation; a persistent Python
SDK worker is the better route for sustained throughput. Keep the same queue
admission limits and one SDK instance per worker after fork.

For video add `--video-profile economy_5s`, `economy_2s` or `resilient`, plus a
truthful audio declaration. The generated [deployment kit](../operations/deployment-kit.md)
provides the verifier/registry path; it is not a public marking SaaS endpoint.

[First export](../start-here.md) · [Worker ownership](../operations/cpu-deployment.md) ·
[Production setup](../operations/production-onboarding.md) · [Samples](../benchmarks/samples.md)
