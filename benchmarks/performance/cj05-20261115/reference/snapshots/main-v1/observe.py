"""Host cgroup observer and sequential protocol driver; run with sudo on EC2.
Root is used ONLY for per-FD reset of this task's container memory.peak counters.
No host config/cache/security settings are changed. No SDK is imported on host.
"""
import collections,fcntl,hashlib,json,os,selectors,shutil,subprocess,sys,time,traceback,uuid
from pathlib import Path
R=Path('/home/ubuntu/ariadne-cj05-20261115');S=R/'scripts';D=R/'data';O=R/'results'
IMAGE='sha256:1a4dd358bcf698df654daaac631a26d3bc874104de5108bc94ce941c33a49980'
O.mkdir(exist_ok=True);HZ=os.sysconf('SC_CLK_TCK');counter=0

def save(path,value):
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)
def emit(event,**kw):
    row={'at_utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'event':event,**kw}
    with (O/'events.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
    print(json.dumps(row),flush=True)

def host():
    line=Path('/proc/stat').read_text().splitlines()[0].split()[1:]
    info={}
    for row in Path('/proc/meminfo').read_text().splitlines():
        if row.startswith(('MemAvailable:','MemTotal:')):k,v,*_=row.split();info[k.rstrip(':')]=int(v)*1024
    return {'cpu_ticks':list(map(int,line)),'loadavg':Path('/proc/loadavg').read_text().strip(),**info}

def kv(path):
    return {a:int(b) for a,b in (line.split()[:2] for line in path.read_text().splitlines())}
def process(pid):
    p=Path('/proc')/str(pid)
    try:
        text=(p/'stat').read_text();tail=text[text.rfind(')')+2:].split();start=int(tail[19]);cpu=(int(tail[11])+int(tail[12]))/HZ
        cmd=(p/'cmdline').read_bytes().split(b'\0');exe=os.path.basename(cmd[0].decode(errors='replace')) if cmd and cmd[0] else (p/'comm').read_text().strip()
        role='node' if exe=='node' else 'ffmpeg' if exe=='ffmpeg' else 'ffprobe' if exe=='ffprobe' else 'python' if 'python' in exe else exe
        status=(p/'status').read_text().splitlines();rss=next((int(x.split()[1])*1024 for x in status if x.startswith('VmRSS:')),0)
        return {'pid':pid,'start_ticks':start,'role':role,'cpu_s':cpu,'rss_bytes':rss,'threads':int(tail[17])}
    except (FileNotFoundError,ProcessLookupError,PermissionError,ValueError):return None

def snapshot(cg):
    cpu=kv(cg/'cpu.stat');memory=int((cg/'memory.current').read_text());mem=kv(cg/'memory.stat')
    processes=[process(int(p)) for p in (cg/'cgroup.procs').read_text().split()];processes=[p for p in processes if p]
    io={};io_devices={}
    for line in (cg/'io.stat').read_text().splitlines():
        parts=line.split();io_devices[parts[0]]={k:int(v) for k,v in (pair.split('=') for pair in parts[1:])}
        for pair in parts[1:]:
            k,v=pair.split('=');io[k]=io.get(k,0)+int(v)
    return {'mono':time.monotonic(),'cpu':cpu,'memory_bytes':memory,'anon_bytes':mem.get('anon',0),'file_bytes':mem.get('file',0),'rss_sum_bytes':sum(p['rss_bytes'] for p in processes),'processes':processes,'io':io,'io_devices':io_devices,'pids':int((cg/'pids.current').read_text())}

def fd_read(fd):os.lseek(fd,0,0);return int(os.read(fd,100).strip())

def delta(a,b):return {k:b.get(k,0)-a.get(k,0) for k in set(a)|set(b)}
class Session:
    def __init__(self,label,exporter=False):
        global counter;counter+=1
        if shutil.disk_usage(R).free < 5*2**30:raise RuntimeError('Disk reserve below 5GiB')
        self.label=label;self.name='ariadne-cj05-'+str(counter)+'-'+uuid.uuid4().hex[:6];self.rows=[]
        self.err=(O/(self.name+'.stderr')).open('w');self.spawn=time.monotonic()
        mounts=['-v',str(S)+':/scripts:ro','-v',str(D/'inputs')+':/inputs:ro','-v',str(D/'public')+':/public:ro',
            '-v',str(D/'artifacts')+':/artifacts'+('' if exporter else ':ro'),'-v',str(D/'registry')+':/registry'+('' if exporter else ':ro')]
        if exporter:mounts+=['-v',str(D/'private')+':/private:ro']
        legacy=Path('/home/ubuntu/ariadne-verifier-r2-20261112/legacy-cache/y_256b_img.jit')
        mounts+=['-v',str(legacy)+':/legacy/y_256b_img.jit:ro','-e','ARIADNE_VIDEOSEAL_MODEL=/legacy/y_256b_img.jit']
        args=['docker','run','--name',self.name,'--network','none','--cpus','2','--memory','4g','--pids-limit','256','--user','1000:1000','--read-only','--tmpfs','/tmp:rw,noexec,nosuid,size=768m','-e','HOME=/tmp','-e','OMP_NUM_THREADS=2','-e','MKL_NUM_THREADS=2','-e','OPENBLAS_NUM_THREADS=2',*mounts,'-i','--entrypoint','python',IMAGE,'/scripts/worker.py']
        self.proc=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.err,text=True,bufsize=1)
        self.selector=selectors.DefaultSelector();self.selector.register(self.proc.stdout,selectors.EVENT_READ)
        if not self.selector.select(60):raise RuntimeError('Worker startup deadline')
        ready=json.loads(self.proc.stdout.readline());assert ready['event']=='ready',ready
        self.startup_wall=time.monotonic()-self.spawn
        detail=json.loads(subprocess.check_output(['docker','inspect',self.name],text=True))[0];assert detail['Image']==IMAGE
        self.pid=detail['State']['Pid'];raw=Path(f'/proc/{self.pid}/cgroup').read_text();sub=next(x[3:] for x in raw.splitlines() if x.startswith('0::'))
        self.cg=Path('/sys/fs/cgroup')/sub.lstrip('/');assert self.name not in str(self.cg) or 'docker' in str(self.cg)
        assert detail['Id'] in str(self.cg),str(self.cg)
        self.startup_cpu=kv(self.cg/'cpu.stat')['usage_usec']/1e6
        self.startup_peak=int((self.cg/'memory.peak').read_text())
        save(O/(self.name+'.container.json'),{'name':self.name,'label':label,'id':detail['Id'],'image':detail['Image'],'limits':{'NanoCpus':detail['HostConfig']['NanoCpus'],'Memory':detail['HostConfig']['Memory']},'cgroup':str(self.cg),'startup_wall_s':self.startup_wall,'startup_cpu_s':self.startup_cpu,'exporter':exporter})
        emit('session_started',session=label,name=self.name,startup_wall_s=round(self.startup_wall,3))
    def request(self,job):
        if shutil.disk_usage(R).free < 5*2**30:raise RuntimeError('Disk reserve below 5GiB')
        before=snapshot(self.cg);h0=host();observer0=time.process_time();fd=os.open(self.cg/'memory.peak',os.O_RDWR)
        os.write(fd,b'0\n');reset_peak=fd_read(fd);assert reset_peak>=0
        started=time.monotonic();last=before;points=[before]
        with (O/(job['id']+'.timeline.jsonl')).open('w') as timeline:
            timeline.write(json.dumps(before)+'\n');self.proc.stdin.write(json.dumps(job)+'\n');self.proc.stdin.flush()
            while True:
                if time.monotonic()-started>1200:raise TimeoutError('Host whole-operation deadline')
                ready=self.selector.select(.1 if job.get('sample_resources',True) else 1200)
                snap=snapshot(self.cg);points.append(snap);timeline.write(json.dumps(snap)+'\n')
                if ready:
                    line=self.proc.stdout.readline()
                    if not line:raise RuntimeError('Worker died: '+str(self.proc.poll()))
                    result=json.loads(line);assert result['id']==job['id'],result;break
            elapsed=time.monotonic()-started
        peak=fd_read(fd);os.close(fd);after=snapshot(self.cg);h1=host();observer=time.process_time()-observer0
        # A live child contributes full CPU counters even when its initial birth
        # was between samples. Reaped children are reported separately by worker.
        startp={(p['pid'],p['start_ticks']):p for p in before['processes']}
        live=collections.defaultdict(float)
        for p in after['processes']:
            if p['role']!='python':live[p['role']]+=p['cpu_s']-startp.get((p['pid'],p['start_ticks']),{}).get('cpu_s',0)
        role_peaks={}
        for point in points+[after]:
            counts=collections.defaultdict(int)
            for p in point['processes']:counts[p['role']]+=p['rss_bytes']
            for k,v in counts.items():role_peaks[k]=max(role_peaks.get(k,0),v)
        ticks=[b-a for a,b in zip(h0['cpu_ticks'],h1['cpu_ticks'])];total=sum(ticks[:8])
        row={'id':job['id'],'session':self.label,'op':job['op'],'case':job.get('case'),'profile':job.get('profile'),'scope':job.get('scope','current'),'iteration':job.get('iteration'),
            'temperature':'process_model_cold' if not self.rows else 'resident_warm',
            'wall_s':elapsed,'cpu_s':(after['cpu']['usage_usec']-before['cpu']['usage_usec'])/1e6,
            'cpu_stat_delta':delta(before['cpu'],after['cpu']),'memory_start_bytes':before['memory_bytes'],'memory_end_bytes':after['memory_bytes'],
            'memory_peak_bytes':peak,'memory_peak_reset_baseline_bytes':reset_peak,'memory_peak_method':'kernel memory.peak reset/read on same FD; includes all cgroup charges',
            'sampled_memory_peak_bytes':max(x['memory_bytes'] for x in points+[after]),'sampled_rss_sum_peak_bytes':max(x['rss_sum_bytes'] for x in points+[after]),
            'sampled_role_rss_peak_bytes':role_peaks,'live_child_cpu_delta_s':dict(live),'io_delta':delta(before['io'],after['io']),
            'resource_sampling_enabled':job.get('sample_resources',True),'sample_count':len(points),'max_pids_threads':max(x['pids'] for x in points),
            'observer_cpu_s':observer,'host_steal_percent':100*ticks[7]/total if total else 0,'host_busy_percent':100*(total-ticks[3]-ticks[4])/total if total else 0,
            'host_available_memory_start_bytes':h0['MemAvailable'],'host_available_memory_end_bytes':h1['MemAvailable'],'host_load_start':h0['loadavg'],'host_load_end':h1['loadavg'],
            'container_startup_wall_s':self.startup_wall if not self.rows else None,'cold_inclusive_wall_s':time.monotonic()-self.spawn if not self.rows else None,
            'cold_inclusive_cpu_s':after['cpu']['usage_usec']/1e6 if not self.rows else None,
            'cold_inclusive_memory_peak_bytes':max(self.startup_peak,peak) if not self.rows else None,
            'worker':result}
        row['cpu_accounting_diagnostic_s']=result.get('python_self_cpu_s',0)+result.get('reaped_children_cpu_s',0)+sum(live.values())
        row['cpu_accounting_difference_s']=row['cpu_s']-row['cpu_accounting_diagnostic_s']
        save(O/(job['id']+'.json'),row)
        with (O/'measurements.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
        self.rows.append(row);save(O/'CHECKPOINT.json',{'last_completed':job['id'],'completed_rows':sum(1 for _ in (O/'measurements.jsonl').open()),'at_utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()})
        emit('operation_completed',id=job['id'],op=job['op'],case=job.get('case'),profile=job.get('profile'),iteration=job.get('iteration'),ok=result['ok'],wall_s=round(elapsed,3),cpu_s=round(row['cpu_s'],3),peak_mib=round(peak/2**20,2),node_cpu_s=round(live.get('node',0),3),reaped_cpu_s=round(result.get('reaped_children_cpu_s',0),3))
        return row
    def close(self):
        try:
            if self.proc.poll() is None:
                self.request({'id':self.name+'-shutdown','op':'close'});self.proc.stdin.write('exit\n');self.proc.stdin.flush();self.proc.wait(timeout=30)
        finally:
            self.err.close();self.selector.close()
            subprocess.run(['docker','stop','--time','10',self.name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)
            subprocess.run(['docker','rm',self.name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)

def calibration():
    s=Session('calibration')
    try:
        c=s.request({'id':'calibration-children','op':'calibrate'});n=s.request({'id':'calibration-reset','op':'noop'})
        assert c['worker']['ok'] and n['worker']['ok']
        assert 'node' in c['sampled_role_rss_peak_bytes'] and 'ffmpeg' in c['sampled_role_rss_peak_bytes']
        assert c['cpu_s'] >= c['worker']['reaped_children_cpu_s']-.03
        assert abs(c['cpu_accounting_difference_s'])<max(.15,c['cpu_s']*.05),c['cpu_accounting_difference_s']
        assert n['memory_peak_bytes']<c['memory_peak_bytes']*.8,('per-FD memory peak did not reset',c['memory_peak_bytes'],n['memory_peak_bytes'])
        save(O/'CALIBRATION.json',{'status':'passed','child_roles_observed':['node','ffmpeg'],'cpu_reference':'self+reaped children, all calibration children exit before response','cpu_cgroup_s':c['cpu_s'],'cpu_reference_s':c['cpu_accounting_diagnostic_s'],'memory_active_peak_bytes':c['memory_peak_bytes'],'memory_idle_reset_peak_bytes':n['memory_peak_bytes'],'memory_per_operation_peak_reset_verified':True})
        emit('calibration_passed')
    finally:s.close()

if __name__=='__main__':
    lock=open('/home/ubuntu/.ariadne-qualification.lock','a');fcntl.flock(lock,fcntl.LOCK_EX)
    mode=sys.argv[1] if len(sys.argv)>1 else 'calibrate'
    try:
        if mode=='calibrate':calibration()
        else:raise ValueError('Campaign driver not yet installed')
    except Exception as e:
        save(O/'FAILURE.json',{'type':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()});emit('failed',error=repr(e));raise
