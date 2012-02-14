
linux, tested on ubtuntu (OSX works too)
better documentation pending, meanwhile for the early adopters:


dependencies & installing:

ccnx

build CCNX per PARC’s instructions for large repo sizes- create a csrc/conf/local.mk that says
PLATCFLAGS= -O2 -D_FILE_OFFSET_BITS=64 -fPIC

ccnr 
pyccn (reorganization branch - https://github.com/remap/PyCCN)


from there, platform specific, incomplete list below:

ubuntu:
gstreamer0.10-plugins-ugly (for x264 encoding)
python-gst0.10-dev (for gst-python)


osX

Install gstreamer & plugins view MacPorts

- install all packages that start with gstreamer (e.g. gstreamer-tools,
  gstreamer-plugins-ffmpg/bad/ugly/good/base) and their dependencies
- install py27-gstreamer
- set to use python from MacPorts as default
- install PyCCN

In play.py change xvimagesink to ximagesink (remove 'v'), this will be fixed later.

