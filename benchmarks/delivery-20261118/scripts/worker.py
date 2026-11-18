"""Measurement worker: unmodified installed SDK; stdin/stdout JSON protocol."""
import json,os,resource,subprocess,sys,time,traceback
from pathlib import Path
sdk=None

def usage():
    a=resource.getrusage(resource.RUSAGE_SELF);b=resource.getrusage(resource.RUSAGE_CHILDREN)
    return {'self_s':a.ru_utime+a.ru_stime,'reaped_s':b.ru_utime+b.ru_stime}

print(json.dumps({'event':'ready','pid':os.getpid()}),flush=True)
for line in sys.stdin:
    job=json.loads(line);started=time.monotonic();u0=usage()
    try:
        op=job['op']
        if op=='noop':time.sleep(.25);result={'ok':True}
        elif op=='calibrate':
            node="const b=Buffer.alloc(134217728,7);const t=Date.now();while(Date.now()-t<1200){for(let i=0;i<b.length;i+=4096)b[i]^=1;}console.log(JSON.stringify(process.cpuUsage()));"
            n=json.loads(subprocess.check_output(['node','-e',node],text=True))
            subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-f','lavfi','-i','testsrc2=size=1280x720:rate=30','-t','2','-threads','2','-c:v','libx264','-preset','fast','-f','null','-'],check=True)
            result={'ok':True,'node_reported_cpu_s':(n['user']+n['system'])/1e6}
        elif op=='close':
            if sdk:sdk.close()
            result={'ok':True}
        else:
            init_s=0.0
            if sdk is None:
                init=time.monotonic()
                from ariadne_mark.pipeline import SDK
                from ariadne_mark.watermark import LazyWatermarker
                from ariadne_mark.videoq import VideoWatermarker
                from ariadne_mark.registry import Registry
                from ariadne_mark.signing import SigningIdentity
                import ariadne_mark
                from importlib.metadata import version
                assert version('ariadne-mark')=='0.7.3a4'
                identity=SigningIdentity.from_directory(Path('/private/identity'),allow_dev=True) if job.get('exporter') else None
                sdk=SDK(identity=identity,marker=LazyWatermarker(threads=2),
                    video_marker=VideoWatermarker(threads=2,profile=job.get('profile') if job.get('profile') in {'economy_5s','economy_2s','resilient'} else 'economy_5s'),
                    registry=Registry(Path('/registry/assets.sqlite3'),read_only=not bool(identity)),
                    trust_anchors=Path('/public/trust.pem'),verification_scope=job.get('scope','current'))
                init_s=time.monotonic()-init
            call=time.monotonic()
            if op=='mark':
                from datetime import datetime
                from ariadne_mark.provenance import ProvenanceRecord,GenerativeSystem,MediaKind,Action
                record=ProvenanceRecord.create(publisher='Ariadne resource benchmark engineering fixtures',
                    system=GenerativeSystem('Pillow or FFmpeg test pattern; not actual AI output','1'),
                    media_kind=MediaKind.VIDEO if job['kind']=='video' else MediaKind.IMAGE,
                    action=Action.CREATED,created_at=datetime.fromisoformat(job['created_at'].replace('Z','+00:00')))
                options={'audio_kind':'none','video_profile':job['profile']} if job['kind']=='video' else {}
                receipt=sdk.mark(Path(job['source']),Path(job['destination']),record,**options)
                result={'ok':True,'receipt':receipt,'sdk_call_s':time.monotonic()-call,'sdk_init_s':init_s}
            elif op=='verify':
                report=sdk.verify(Path(job['source']))
                result={'ok':True,'report':report,'sdk_call_s':time.monotonic()-call,'sdk_init_s':init_s}
            else:raise ValueError('Unknown operation')
        u1=usage();response={'event':'result','id':job['id'],'worker_operation_s':time.monotonic()-started,
             'python_self_cpu_s':u1['self_s']-u0['self_s'],'reaped_children_cpu_s':u1['reaped_s']-u0['reaped_s'],**result}
    except Exception as exc:
        u1=usage();response={'event':'result','id':job['id'],'ok':False,'worker_operation_s':time.monotonic()-started,
            'python_self_cpu_s':u1['self_s']-u0['self_s'],'reaped_children_cpu_s':u1['reaped_s']-u0['reaped_s'],
            'error':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
    print(json.dumps(response),flush=True)
    if job['op']=='close':
        sys.stdin.readline()
        break
