#! /usr/bin/env python

import pygst
pygst.require("0.10")
import gst
import gobject

import sys
import audio_sink, video_sink
import audio_src, video_src

if __name__ == '__main__':
	gobject.threads_init()

	if len(sys.argv) < 2:
		print >> sys.stderr, "ERROR: pipeline could not be constructed: empty pipeline not allowed."
		sys.exit(1)

	args = " ".join(sys.argv[1:])
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
