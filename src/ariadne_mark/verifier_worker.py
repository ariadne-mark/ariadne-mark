"""Private local verification worker; framed JSON, no network protocol."""
import json
import os
import struct
import sys

MAX_MESSAGE = 8 * 1024 * 1024


def read_message(stream, *, limit=65536):
    def exact(size):
        data = bytearray()
        while len(data) < size:
            chunk = stream.read(size - len(data))
            if not chunk:
                raise EOFError('worker_channel_closed')
            data.extend(chunk)
        return bytes(data)
    size = struct.unpack('>I', exact(4))[0]
    if not 0 < size <= limit:
        raise ValueError('worker_message_size')
    return json.loads(exact(size))


def send_message(stream, value):
    data = json.dumps(value, allow_nan=False).encode()
    if len(data) > MAX_MESSAGE:
        raise ValueError('worker_response_size')
    stream.write(struct.pack('>I', len(data)) + data)
    stream.flush()


def main():
    # Keep the protocol's own FD; discard any third-party/native stdout too.
    channel = os.fdopen(os.dup(sys.stdout.fileno()), 'wb', buffering=0)
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    sdk = None
    try:
        config = read_message(sys.stdin.buffer)
        if set(config) != {'threads', 'registry', 'trust_anchors', 'tsa_trust_anchors'}:
            raise ValueError('worker_config')
        from pathlib import Path
        from ariadne_mark.pipeline import SDK
        from ariadne_mark.registry import Registry
        from ariadne_mark.watermark import LazyWatermarker
        from ariadne_mark.videoq import VideoWatermarker
        sdk = SDK(LazyWatermarker(threads=config['threads']),
                  registry=Registry(Path(config['registry']), read_only=True) if config['registry'] else None,
                  trust_anchors=Path(config['trust_anchors']) if config['trust_anchors'] else None,
                  tsa_trust_anchors=Path(config['tsa_trust_anchors']) if config['tsa_trust_anchors'] else None,
                  video_marker=VideoWatermarker(threads=config['threads']))
        send_message(channel, {'ready': True})
        while True:
            command = read_message(sys.stdin.buffer)
            if set(command) != {'id', 'path'} or type(command['id']) is not int or not isinstance(command['path'], str):
                raise ValueError('worker_request')
            try:
                report = sdk.verify(Path(command['path']))
                send_message(channel, {'id': command['id'], 'report': report})
            except Exception:
                # No file paths, metadata values or exception messages cross IPC.
                send_message(channel, {'id': command['id'], 'error': 'verification_failed'})
    except EOFError:
        pass
    except Exception as exc:
        from ariadne_mark.errors import C2paRuntimeMismatch
        if sdk is None and isinstance(exc, C2paRuntimeMismatch):
            send_message(channel, {'ready': False, 'error': 'c2pa_runtime_unqualified', 'runtime': exc.report})
        else:
            raise
    finally:
        if sdk is not None:
            sdk.close()
        channel.close()


if __name__ == '__main__':
    main()
