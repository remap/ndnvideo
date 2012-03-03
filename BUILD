
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

Install gstreamer & plugins view MacPorts:

sudo port install gst-ffmpeg gst-plugins-bad gst-plugins-base gst-plugins-gl gst-plugins-gl gst-plugins-gl gst-plugins-good gst-plugins-ugly gst-rtsp-server gstreamer py27-gst-python

- install PyCCN

In play.py change xvimagesink to ximagesink (remove 'v'), this will be fixed later.


testing:

To make sure gst works you can try:

gst-launch videotestsrc ! ximagesink
gst-launch v4l2src ! ximagesink
gst-launch v4l2src ! x264enc ! ffdec_h264 ! ximagesink


To check that python bindings are available do:

$ python
import pygst


Troubleshooting:

if you get "No module named pygtk" then this most likely means that the python you're using is the one that
comes with MacOS X. Unfortunately the Mac Ports packages aren't visible
by default to that python, you could probably set up PYTHONPATH to point
there but probably is easier to just use the python from macports.


