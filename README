README:

This is a video toolkit it publishes and plays live video in a segmented stream
that also seeks from buffer in CCNx repo.

more detailed readme to come; meanwhile this should help the early adopters.

ignore /sandbox, this readme applies to just /videostreaming folder

installing:

	see 'BUILD'

usage:

playing remote stream:

make sure ccnd is running, and has a route to a testbed node.


./play.py /ndn/ucla.edu/apps/video


if that doesn't work, see 'troubleshooting', below. 


publishing local video:

make sure CCNR_DIRECTORY is set and sourced (we recommend to define it in ~/.profile)
make sure ccnd & ccnr (your local repo) are running, and are routed (for others to access)

note:  you may need to manually create CCNR_DIRECTORY/import/ directory


if you don't have a working video URI, there are a few options:

1) python video_sink.py [desired URI]

then you have a URI you can play via above. It auto-selects first video device.

another option is 
2) the more featured 'publish' script:

python ./publish.py [URI] m

as of writing, this uses /dev/video0.

yet another option is to use a file instead of a capture device:
3) ./ccn_launch.py filesrc location=[filename.mp4] ! typefind ! qtdemux name=mux \
mux.video_00 ! queue ! VideoSink location=/repo/test/mainvideo/video \
mux.audio_00 ! queue ! AudioSink location=/repo/test/mainvideo/audio

Troubleshooting:

make sure gstreamer works independently of ndnvideo.

for instance, sudo apt-get install gstreamer-tools
 then 

ie - try

gst-launch -v -m autovideosrc ! xvimagesink

if this doesn't work, try 
xvinfo
if you don't have any adapters… you can likely use ximagesink.

however you may need to videoscale to specific supported size listed by: 

gst-inspect ximagesink

can also try:

./ccn_launch.py VideoSrc location=/ndn/ucla.edu/apps/video/hydra/ ! \
   ffdec_h264 ! aasink

(this will render video using ascii :)
