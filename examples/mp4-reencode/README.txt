Public Ariadne sample: https://ariadnemark.xyz/assets/c2pa-proof/files/economy_5s.mp4
FFmpeg 6.1.1 on Linux:
ffmpeg -i signed.mp4 -map 0:v:0 -an -c:v libx264 -crf 23 -preset medium -threads 1 -pix_fmt yuv420p -map_metadata -1 -movflags +faststart reencoded.mp4
Checks: https://ariadnemark.xyz/verify/
The packaged JSON files are excerpts from the public verifier responses. The original has a development signature.
