README:

this is a video toolkit…  it publishes and plays live video in a segmented stream that also seeks from buffer in repository.

more detailed readme to come; meanwhile this should help the early adopters. 

ignore /sandbox, this readme applies to just /videostreaming folder

dependencies:

ccnx
ccnr 
pyccn (reorganization branch - https://github.com/remap/PyCCN)

ubuntu:
gstreamer0.10-plugins-ugly (for x264 encoding)
python-gst0.10-dev (for gst-python)

linux, tested on ubtuntu (OSX works, documentation pending)

usage:

local testing:

make sure CCNR_DIRECTORY is set and sourced (recommend ~/.profile)
make sure ccnx & ccnr (your local repo) are running. 

if you have a known working video URI, just type

python play.py [URI]

if that doesn't work, see 'troubleshooting', below. 

if you don't have a working video URI, make one with video_sink:

python video_sink.py

then you have a local URL based on your device name, you can then play that. 

(use ccnexplore to find the URI if needed)

note:  you may need to manually create CCNR_DIRECTORY/import/ directory


Troubleshooting:

make sure gstreamer works independently of ndnvideo.

for instance, sudo apt-get install gstreamer-tools
 then 

ie - try

gst-launch -v -m autovideosrc ! xvimagesink

if this doesn't work, try 
xvinfo
if you don't have any adapters… you'll need a better video card and driver!

you may be able to get by with ximagesink, however you may need to videoscale to specific supported size listed by:
gst-inspect ximagesink

if video is of wrong size you might need to
            use videoscale to scale it to right resolution.


./ccn_launch.py VideoSrc location=/ndn/ucla.edu/apps/hydra/video ! \
   ffdec_h264 ! aasink

(this will render video using ascii :)
