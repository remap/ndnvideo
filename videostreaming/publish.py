#! /usr/bin/env python

import pygst
pygst.require("0.10")
import gst
import gobject

import sys
import os
import time
import pyccn

import utils
from video_sink import VideoSink
from audio_sink import AudioSink

def usage(argv0):
	print "Usage: %s <uri> <devices> [pidfile]" % argv0

def main(args):
	gobject.threads_init()

	if len(args) not in [3, 4]:
		usage(args[0])
		return 1

	uri = pyccn.Name(args[1])
	mode = []
	mode += args[2]
	pidfile = "publish.pid" if len(args) == 3 else args[3]

	uri = uri.appendVersion()

	video_pipe = """v4l2src device=%s ! video/x-raw-yuv,width=%d,height=%d ! aspectratiocrop aspect-ratio=4/3 !
		deinterlace mode=1 method=4 fields=top ! videorate ! timeoverlay shaded-background=true valignment=bottom ! \
		clockoverlay shaded-background=true halignment=right valignment=bottom !
		x264enc byte-stream=true bitrate=%d qp-max=30 interlaced=true ! VideoSink location=%s"""
	audio_pipe = "autoaudiosrc ! lamemp3enc bitrate=%d ! AudioSink location=%s"

	pipes = {}
	pipes['a'] = audio_pipe % (128, uri + "audio")
	pipes['v'] = video_pipe % ("/dev/video0", 704, 480, 1024, uri + "video")
	pipes['1'] = video_pipe % ("/dev/video1", 352, 240, 256, uri + "video1")
	pipes['2'] = video_pipe % ("/dev/video2", 352, 240, 256, uri + "video2")
	pipes['3'] = video_pipe % ("/dev/video3", 352, 240, 256, uri + "video3")
	pipes['4'] = video_pipe % ("/dev/video4", 352, 240, 256, uri + "video4")

	p = []
	for m in mode:
		p.append(pipes[m])

	of = open(pidfile, "w")
	of.write(str(os.getpid()))
	of.close()

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

if __name__ == "__main__":
	sys.exit(main(sys.argv))

