#! /usr/bin/env python

import pygst
pygst.require("0.10")
import gst
import gobject

import sys
import audio_sink, video_sink
import audio_src, video_src

import player

if __name__ == '__main__':
	gobject.threads_init()

	if len(sys.argv) < 2:
		print >> sys.stderr, "ERROR: pipeline could not be constructed: empty pipeline not allowed.\n\nUsage:"
		print >> sys.stderr, "for progress logging:"
		print >> sys.stderr, "./ccn_launch_latest.py [videoURI] \n"
		print >> sys.stderr, "or for ascii playback:"
		print >> sys.stderr, "./ccn_launch_latest.py [videoURI] ascii"
		sys.exit(1)

	name = player.get_latest_version(sys.argv[1])
	
	if name is None:
		print "No content found at %s" % cmd_args.URI

	# build pipelines for both realtime progress logging & ascii view

	PROG = "VideoSrc location="+str(name)+"/video ! progressreport ! fakesink sync=true"
	ASCII = "VideoSrc location="+str(name)+"/video ! ffdec_h264 ! aasink"
	
	print "arg len is "+str(len(sys.argv))
	
	if(len(sys.argv) == 3):
		if (sys.argv[2] == "ascii"):
			args = ASCII
	else:
		args = PROG
	
	#args = " ".join(sys.argv[1:])
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
