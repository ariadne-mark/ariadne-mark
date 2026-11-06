# Apply marking to the final rendition

For an app generating several layouts, run the SDK after preparing each final
layout. This is the simplest practical way to avoid destroying a watermark in
your own export chain. It uses the existing SDK and the same three presets.

1. Generate/edit the content.
2. Produce the final crop, aspect ratio, size and any baked-in graphics.
3. Mark/sign each resulting file with the SDK; use a separate asset record and
   output for each rendition. Keep the final export gate enabled.
4. Publish the returned file and receipt without another uncontrolled edit.

For example, generate the landscape and portrait renders first, then call
`sdk.mark` for each. Avoid marking a landscape master and subsequently cropping
that marked master to portrait. Native portrait marking and recovery after
removing most of a marked landscape image are different technical problems.

If the delivery pipeline must transform the file again, qualify those exact
transforms and retain/regenerate appropriate provenance. A fresh-output gate
only checks the SDK output, not every later platform upload/download. Existing
signatures bind their original asset; they do not automatically authenticate an
edited copy. Capturing common renditions at final export reduces avoidable
geometry loss, but is not a promise about arbitrary downstream crops or edits.

Supported boundaries, selected-frame policy and read-back scope remain in the
[video guide](video-profiles.md). Experimental post-letterbox recovery and new
localization models are tracked in the [spatial research](../research/spatial-recovery-2026-11-06.md).

With FFmpeg, make square pixels explicit after preparing a rendition. For example,
`crop=trunc(ih*9/16/2)*2:ih,scale=720:1280,setsar=1` produces a square-pixel
portrait input. A scale operation may otherwise preserve display aspect through
a non-square sample aspect ratio; the SDK deliberately requires explicit
normalization rather than silently interpreting it as square pixels.
