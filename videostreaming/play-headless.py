#! /usr/bin/env python

import pygst
pygst.require("0.10")
import gst
import gobject

import sys
import audio_sink, video_sink
import audio_src, video_src

import player

def usage(argv0):
	print >> sys.stderr, "Usage:"
	print >> sys.stderr, "for progress logging:"
	print >> sys.stderr, "%s [videoURI]\n" % argv0
	print >> sys.stderr, "or for ascii playback:"
	print >> sys.stderr, "%s [videoURI] ascii" % argv0

def main(args):
	gobject.threads_init()

	if len(args) < 2:
		usage(args[0])
		return 1

	name = player.get_latest_version(args[1])
	if name is None:
		print "No content found at %s" % args[1]
		return 1

	# build pipelines for both realtime progress logging & ascii view
	PROG = "VideoSrc location=%s/video ! progressreport ! fakesink sync=true" % name
	ASCII = "VideoSrc location=%s/video ! ffdec_h264 ! aasink" % name

	if len(args) == 3 and args[2] == "ascii":
		args = ASCII
	else:
		args = PROG

	pipeline = gst.parse_launch(args)

	loop = gobject.MainLoop()
	pipeline.set_state(gst.STATE_PLAYING)

	try:
		loop.run()
	except KeyboardInterrupt:
		print "Ctrl+C pressed, exitting"
		pass

	pipeline.set_state(gst.STATE_NULL)
	pipeline.get_state(gst.CLOCK_TIME_NONE)

if __name__ == '__main__':
	sys.exit(main(sys.argv))
