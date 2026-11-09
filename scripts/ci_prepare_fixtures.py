"""Small deterministic install-smoke fixtures, not a robustness benchmark."""
from pathlib import Path
import subprocess
import sys
import numpy as np
from PIL import Image
root=Path(sys.argv[1]);root.mkdir(parents=True,exist_ok=True)
rng=np.random.default_rng(42);pixels=np.zeros((320,512,3),dtype=np.float32)
for side,amplitude in ((4,35),(16,30),(64,20),(256,10)):
    image=Image.fromarray(rng.integers(0,256,(side,side,3),dtype=np.uint8))
    pixels+=(np.asarray(image.resize((512,320),Image.Resampling.BICUBIC),dtype=np.float32)-128)*amplitude/128
image=Image.fromarray(np.clip(128+pixels,0,255).astype('uint8'));image.save(root/'input.png')
subprocess.run(['ffmpeg','-v','error','-y','-loop','1','-framerate','12','-i',str(root/'input.png'),
    '-t','2','-c:v','libx264','-threads','2','-pix_fmt','yuv420p','-crf','18',str(root/'input.mp4')],check=True)
