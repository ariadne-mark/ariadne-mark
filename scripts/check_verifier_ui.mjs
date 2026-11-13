import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const fields = new Map();
function element() {return {textContent:'', hidden:false, children:[], append(...xs){this.children.push(...xs);},replaceChildren(){this.children=[];},addEventListener(){},focus(){},files:[]};}
const document={getElementById(id){if(!fields.has(id))fields.set(id,element());return fields.get(id);},createElement:element,querySelectorAll(){return [];}};
const ctx=vm.createContext({document,fetch:async()=>({json:async()=>({max_upload_bytes:1024})}),console,setTimeout,clearTimeout,URL,Blob,AbortController});
vm.runInContext(fs.readFileSync(new URL('../src/ariadne_mark/verifier_assets/app.js',import.meta.url),'utf8'),ctx);
const id='014d123456789abc';
const report={label:'Watermark ID recovered; sampled video evidence only',c2pa:{status:'not_found'},watermark:{status:'recovered_claim',token:id,ids:[{token:id,status:'confirmed',first_time_s:0,last_time_s:0.0417}],evidence_scope:{whole_file_examined:false,passes:[{algorithm:'adobe.trustmark.Q.variax-bch5',selection:'sequential_from_start',stop_reason:'two_concordant_ids'}]},out_of_operator_scope:['meta.videoseal.1.0.bch20']},recovery:{status:'found',record:{publisher:'Reviewed Provider'},content_binding:'not_verified'},signed_id_observed:false};
ctx.report=report;vm.runInContext('render(report)',ctx);
let shown=fields.get('provenance').children.map(x=>x.textContent).join('\n');
assert.match(shown,/first read 0\.00 s · last read 0\.04 s · sampled positions only/);assert.match(shown,/rest of the file is not established/);assert.match(shown,/stop: two_concordant_ids/);assert.match(shown,/not observed in this scan/);
report.watermark={status:'multiple_ids',ids:[{token:id,status:'observed',first_time_s:2,last_time_s:2}],evidence_scope:{passes:[]}};
vm.runInContext('render(report)',ctx);shown=fields.get('provenance').children.map(x=>x.textContent).join('\n');assert.match(shown,/unconfirmed/);assert.doesNotMatch(shown,/single read/);
console.log(JSON.stringify({ok:true,single_id_positions:true,scan_scope:true,signed_id_observed:true,unconfirmed_wording:true}));
