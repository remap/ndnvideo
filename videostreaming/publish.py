#! /usr/bin/env python

import pygst
pygst.require("0.10")
import gst
import gobject

import sys
import time
import pyccn

import utils
from video_sink import VideoSink
from audio_sink import AudioSink

def usage():
	print "Usage: %s <uri> m|1|2|3|4" % sys.argv[0]
	sys.exit(1)

if __name__ == "__main__":
	gobject.threads_init()

	if len(sys.argv) != 3:
		usage()

	uri = pyccn.Name(sys.argv[1])
	mode = sys.argv[2]

	#uri = uri + time.strftime("%Y%m%d%H%M%S")
	uri = uri.appendVersion()

	video_pipe = "v4l2src device=%s ! video/x-raw-yuv,width=%d,height=%d ! aspectratiocrop aspect-ratio=4/3 ! deinterlace mode=1 method=4 fields=top ! videorate ! \
                timeoverlay shaded-background=true valignment=bottom ! \
		clockoverlay shaded-background=true halignment=right valignment=bottom ! \
		x264enc byte-stream=true bitrate=%d qp-max=30 interlaced=true ! VideoSink location=%s"
	audio_pipe = "autoaudiosrc ! lamemp3enc bitrate=%d mono=true ! AudioSink location=%s"

	pipes = {}
	pipes['m'] = video_pipe % ("/dev/video0", 704, 480, 1024, uri + "mainvideo" + "video") + " " + audio_pipe % (128, uri + "mainvideo" + "audio")
	#pipes['m2'] = video_pipe % ("/dev/video0", 704, 480, 512, uri + "mainvideo" + "video2")
	#pipes['1'] = video_pipe % ("/dev/video1", 352, 240, 256, uri + "video1")
	#pipes['2'] = video_pipe % ("/dev/video2", 352, 240, 256, uri + "video2")
	#pipes['3'] = video_pipe % ("/dev/video3", 352, 240, 256, uri + "video3")
	#pipes['4'] = video_pipe % ("/dev/video4", 352, 240, 256, uri + "video4")

	#pipeline = gst.parse_launch(pipes[mode])
	p = []
	p.append(pipes['m'])
	#p.append(pipes['m2'])
	#p.append(pipes['1'])
	#p.append(pipes['2'])
	#p.append(pipes['3'])
	#p.append(pipes['4'])
	pipeline = gst.parse_launch(" ".join(p))

	loop = gobject.MainLoop()
	pipeline.set_state(gst.STATE_PLAYING)

	try:
		loop.run()
	except KeyboardInterrupt:
		print "Ctrl+C pressed; exiting"
		pass

	pipeline.set_state(gst.STATE_NULL)
	pipeline.get_state(gst.CLOCK_TIME_NONE)

