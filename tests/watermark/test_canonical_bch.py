"""Actual upstream codec correction radius and canonical rejection."""
import os,unittest


@unittest.skipUnless(os.environ.get('ARIADNE_MEDIA_TESTS')=='1','requires pinned upstream codecs')
class CanonicalBCHTests(unittest.TestCase):
    def test_python_five_errors_and_noncanonical_upstream_acceptances(self):
        import numpy as np
        from trustmark.datalayer import DataLayer
        from ariadne_mark.watermark.canonical import CanonicalBCH5
        layer=DataLayer(100,verbose=False,encoding_mode=1)
        guard=CanonicalBCH5(layer);rng=np.random.default_rng(7241)
        for count in range(6):
            for _ in range(20):
                payload=''.join(map(str,rng.integers(0,2,61)))
                raw=layer.encode_binary([payload]);indices=rng.choice(96,count,replace=False)
                raw[0,indices]=1-raw[0,indices]
                bits,present,schema=guard.decode_bitstream(raw)[0]
                self.assertTrue(present,(count,indices))
                self.assertEqual(bits,payload)
                self.assertEqual(schema,1)
        rejected=0
        for _ in range(1000):
            raw=rng.integers(0,2,(1,100));raw[0,-4:]=[0,0,0,1]
            original=layer.decode_bitstream(raw,MODE='binary')[0]
            checked=guard.decode_bitstream(raw)[0]
            if original[1] and not checked[1]:rejected+=1
            if checked[1]:
                canonical=layer.encode_binary([checked[0]])[0]
                self.assertLessEqual(sum(a!=b for a,b in zip(raw[0,:96],canonical[:96])),5)
        # Exercise an invalid upstream success deterministically; random inputs
        # are controls, not a guarantee of reproducing a rare decoder defect.
        payload='0'*61
        raw=layer.encode_binary([payload]);raw[0,:6]=1-raw[0,:6]
        class IncorrectSuccess:
            def encode_binary(self,bits):return layer.encode_binary(bits)
            def decode_bitstream(self,packets,MODE):return [(payload,True,1)]
        self.assertFalse(CanonicalBCH5(IncorrectSuccess()).decode_bitstream(raw)[0][1])

    def test_node_uses_actual_pinned_codec(self):
        import subprocess
        from pathlib import Path
        from ariadne_mark.videoq import ROOT,data_dir
        code="""
import {createRequire} from 'node:module';
const require=createRequire(process.argv[1]+'/runtime/package.json');
const {DataLayer}=require('@variax-ai/video-watermark');
const {canonicalPacket}=await import(process.argv[2]+'/canonical.mjs');
const dl=new DataLayer();let seed=7241;
function bit(){seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed>>>31;}
let rejected=0;
for(let n=0;n<1000;n++){
 const data=Uint8Array.from({length:61},bit);const raw=dl.encode(data,'BCH_5');
 for(let j=0;j<n%6;j++)raw[(j*17+n)%96]^=1;
 const checked=canonicalPacket(dl,raw);
 if(!checked||String(checked.data)!==String(data))throw Error('valid correction rejected');
 const noise=Uint8Array.from({length:100},bit);noise.set([0,0,0,1],96);
 const old=dl.decode(noise);if(old.valid&&old.schema==='BCH_5'&&!canonicalPacket(dl,noise))rejected++;
}
const data=new Uint8Array(61),bad=dl.encode(data,'BCH_5');
for(let i=0;i<6;i++)bad[i]^=1;
const incorrect={decode:()=>({valid:true,schema:'BCH_5',data}),encode:(d,s)=>dl.encode(d,s)};
if(canonicalPacket(incorrect,bad)!==null)throw Error('invalid upstream success accepted');
console.log(JSON.stringify({valid_corrections:1000,noncanonical_rejected:rejected}));
"""
        result=subprocess.run(['node','--input-type=module','-e',code,str(data_dir()),str(ROOT)],capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('noncanonical_rejected',result.stdout)
