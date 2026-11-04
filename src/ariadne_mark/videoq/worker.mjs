// Binary framed IPC; upstream Variax0.3.2 algorithm with pinned alias fix.
import {createRequire} from 'node:module';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
const [runtimeDir,modelDir,threads]=process.argv.slice(2);
const require=createRequire(join(runtimeDir,'package.json'));
const {Watermarker,DataLayer,createRuntime}=require('@variax-ai/video-watermark');
const ort=require('onnxruntime-node');
let calls=0,inferenceMs=0;
const inner=createRuntime(ort,{intraOpNumThreads:Number(threads),interOpNumThreads:1,executionProviders:['cpu']});
const runtime={async createSession(bytes){const s=await inner.createSession(bytes);return {async run(feeds){const t=performance.now();const r=await s.run(feeds);calls++;inferenceMs+=performance.now()-t;return r;}}}};
const wm=await Watermarker.create({variant:'Q',models:{encoder:readFileSync(join(modelDir,'encoder_Q.onnx')),decoder:readFileSync(join(modelDir,'decoder_Q.onnx'))},runtime});
const dl=new DataLayer();
function unpack(d){if(!d.valid||d.schema!=='BCH_5')return null;let id=0n;for(const bit of d.data)id=(id<<1n)|BigInt(bit);return (id>>48n)===0x14dn?id.toString(16).padStart(16,'0'):null;}
function packet(logits){return unpack(dl.decode(Uint8Array.from(logits,x=>x>0?1:0)));}
let carry=Buffer.alloc(0),eof=false,waiting;
process.stdin.on('data',b=>{carry=Buffer.concat([carry,b]);waiting?.();waiting=null;});
process.stdin.on('end',()=>{eof=true;waiting?.();waiting=null;});
async function read(n){while(carry.length<n){if(eof){if(carry.length===0)return null;throw Error('truncated input');}await new Promise(r=>waiting=r);}const b=carry.subarray(0,n);carry=carry.subarray(n);return b;}
async function send(data,body=Buffer.alloc(0)){const json=Buffer.from(JSON.stringify({...data,n:body.length}));const head=Buffer.alloc(4);head.writeUInt32BE(json.length);for(const b of [head,json,body])if(!process.stdout.write(b))await new Promise(r=>process.stdout.once('drain',r));}
let iterator=null,queue=null,state=null;
async function reset(){if(iterator)await iterator.return();iterator=null;queue=null;}
// The source generator must remain suspended after each yield; keep it open
// between commands rather than ending at an empty queue.
class FrameQueue {items=[];waiter=null;push(x){if(this.waiter){this.waiter(x);this.waiter=null;}else this.items.push(x);}async *frames(){while(true)yield this.items.length?this.items.shift():await new Promise(r=>this.waiter=r);}}
await send({ready:true});
while(true){const size=await read(4);if(!size)break;const len=size.readUInt32BE();if(len>65536)throw Error('header too large');const raw=await read(len);const c=JSON.parse(raw.toString());if(!Number.isInteger(c.n)||c.n<0||c.n>67108864)throw Error('invalid payload size');const body=await read(c.n)||Buffer.alloc(0);
 try{
  if(c.op==='begin'){
   if(!['fast','resilient'].includes(c.profile)||!/^014d[0-9a-f]{12}$/.test(c.token))throw Error('invalid profile/token');
   await reset();state={profile:c.profile,token:c.token,frames:0,startCalls:calls,startMs:inferenceMs};await send({ok:true});
  }else if(c.op==='encode'||c.op==='decode'){
   if(!Number.isInteger(c.width)||!Number.isInteger(c.height)||Math.min(c.width,c.height)<256||Math.max(c.width,c.height)>4096||body.length!==c.width*c.height*4)throw Error('invalid frame dimensions');
   const f={width:c.width,height:c.height,data:new Uint8ClampedArray(body)};
   if(c.op==='decode'){const logits=await wm.decodeFrame(f);await send({token:packet(logits),logits:Array.from(logits)});continue;}
   if(!state)throw Error('begin required');
   if(!iterator||state.frames%24===0){await reset();queue=new FrameQueue();iterator=wm.embedFrames(queue.frames(),{contentId:BigInt('0x'+state.token)},{strategy:state.profile==='fast'?'sharedResidual':'perFrame',schema:'BCH_5',strength:1,inPlace:true,sceneChangeThreshold:.10});}
   queue.push(f);const next=await iterator.next();if(next.done)throw Error('incomplete frame');state.frames++;await send({ok:true},Buffer.from(next.value.data));
  }else if(c.op==='aggregate'){
   if(!Array.isArray(c.logits)||c.logits.length>20)throw Error('invalid samples');const totals=new Float32Array(100);
   for(const row of c.logits){if(row.length!==100||!row.every(Number.isFinite))throw Error('invalid logits');for(let i=0;i<100;i++)totals[i]+=row[i];}
   const d=dl.decode(Uint8Array.from(totals,x=>x>=0?1:0));await send({token:unpack(d)});
  }else if(c.op==='end'){
   await reset();const stats=state?{frames:state.frames,inference_calls:calls-state.startCalls,inference_s:(inferenceMs-state.startMs)/1000,profile:state.profile}:{};state=null;await send(stats);
  }else throw Error('unknown operation');
 }catch(e){await reset();state=null;await send({error:String(e)});}
}
