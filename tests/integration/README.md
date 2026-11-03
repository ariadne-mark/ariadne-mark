# Real-engine integration tests

Enable `ARIADNE_MEDIA_TESTS=1` in the built CPU Docker image. [test_media.py](test_media.py) uses actual TrustMark, C2PA and FFmpeg rather than mocked optional engines. The default core-only suite skips these tests; the required CI media job runs them.
