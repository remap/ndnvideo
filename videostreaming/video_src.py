#! /usr/bin/env python

import pygst
pygst.require("0.10")
import gst
import gobject

import Queue, traceback
import pyccn

import utils
from ElementBase import CCNDepacketizer

CMD_SEEK = 1

def debug(cls, text):
	print "%s: %s" % (cls.__class__.__name__, text)

class CCNVideoDepacketizer(CCNDepacketizer):
	def __init__(self, uri):
		CCNDepacketizer.__init__(self, uri)
		self._tc = None

	def post_fetch_stream_info(self, caps):
		framerate = caps[0]['framerate']
		self._tc = utils.TCConverter(framerate)

	def ts2index(self, ts):
		return self._tc.ts2tc(ts)

	def ts2index_add_1(self, ts):
		tc = self._tc.ts2tc_obj(ts)
		tc.next()
		return tc.make_timecode()

	def index2ts(self, index):
		return self._tc.tc2ts(index)

class VideoSrc(gst.BaseSrc):
	__gtype_name__ = 'VideoSrc'
	__gstdetails__ = ("CCN Video Source", "Source/Network",
		"Receives video data over a CCNx network", "Derek Kulinski <takeda@takeda.tk>")

	__gsttemplates__ = (
		gst.PadTemplate("src",
			gst.PAD_SRC,
			gst.PAD_ALWAYS,
			gst.caps_new_any()),
		)

	__gproperties__ = {
		'location' : (gobject.TYPE_STRING,
			'CCNx location',
			'location of the stream in CCNx network',
			'',
			gobject.PARAM_READWRITE)
	}

	def __init__(self):
		gst.BaseSrc.__init__(self)
		self.depacketizer = None
		self.set_format(gst.FORMAT_TIME)
		self.seek_in_progress = None
		self._no_locking = False

	def do_set_property(self, property, value):
		if property.name == 'location':
			self.depacketizer = CCNVideoDepacketizer(value)
		else:
			raise AttributeError, 'unknown property %s' % property.name

	def do_get_caps(self):
		debug(self, "Called do_get_caps")
		if self.depacketizer:
			return self.depacketizer.get_caps()
		return None

	def do_start(self):
		debug(self, "Called start")
		self.depacketizer.start()
		return True

	def do_stop(self):
		debug(self, "Called stop")
		self.depacketizer.stop()
		return True

	def do_is_seekable(self):
		debug(self, "is seekable")
		return True

#	def do_event(self, event):
#		if event.type == gst.EVENT_QOS:
#			print "QOS: proportion: %f diff: %d timestamp: %d" % event.parse_qos()
#		else:
#			print "Got event %s" % event.type
#		return gst.BaseSrc.do_event(self, event)

	def do_create(self, offset, size):
		if self._no_locking:
			return gst.FLOW_WRONG_STATE, None

		#debug(self, "Offset: %d, Size: %d" % (offset, size))
		try:
			while True:
				try:
					status, buffer = self.depacketizer.queue.get(True, 1)
					#print "%d %d %d %s" % (buffer.timestamp, buffer.duration, buffer.flags, buffer.caps)
				except Queue.Empty:
					if self._no_locking:
						return gst.FLOW_WRONG_STATE, None
					else:
						debug(self, "Starving for data")
						continue

				if self._no_locking:
					self.depacketizer.queue.task_done()
					return gst.FLOW_WRONG_STATE, None

				if self.seek_in_progress is not None:
					if status != CMD_SEEK:
						debug(self, "Skipping prefetched junk ...")
						self.depacketizer.queue.task_done()
						continue

					debug(self, "Pushing seek'd buffer")
					event = gst.event_new_new_segment(False, 1.0, gst.FORMAT_TIME,
					                                  self.seek_in_progress, -1,
					                                  self.seek_in_progress)
					r = self.get_static_pad("src").push_event(event)
					debug(self, "Result of announcement of the new segment: %s" % r)

					self.seek_in_progress = None
					buffer.flag_set(gst.BUFFER_FLAG_DISCONT)

				self.depacketizer.queue.task_done()
				return gst.FLOW_OK, buffer
		except:
			traceback.print_exc()
			return gst.FLOW_ERROR, None

	def do_do_seek(self, segment):
		debug(self, "Asked to seek to %d" % segment.start)
		self.seek_in_progress = segment.start
		pos = self.depacketizer.seek(segment.start)
		return True

	def do_query(self, query):
		if query.type != gst.QUERY_DURATION:
			return gst.BaseSrc.do_query(self, query)

		duration = self.depacketizer.duration_ns

		if not duration:
			return True

		query.set_duration(gst.FORMAT_TIME, duration)

		#debug(self, "Returning %s %d" % (query.parse_duration()))

		return True

	def do_check_get_range(self):
		debug(self, "get range")
		return False

	def do_unlock(self):
		debug(self, "Unlock!!!")
		self._no_locking = True
		return True

	def do_unlock_stop(self):
		debug(self, "Stop unlocking!!!")
		self._no_locking = False
		return True

gst.element_register(VideoSrc, 'VideoSrc')

if __name__ == '__main__':
	import sys

	gobject.threads_init()

	if len(sys.argv) != 2:
		print "Usage: %s <uri>" % sys.argv[0]
		exit(1)

	uri = sys.argv[1]

	pipeline = gst.parse_launch('VideoSrc location=%s ! ffdec_h264 max-threads=3 ! xvimagesink' % uri)

	loop = gobject.MainLoop()

	pipeline.set_state(gst.STATE_PLAYING)
	print "Entering loop"

	try:
		loop.run()
	except KeyboardInterrupt:
		print "Ctrl+C pressed, exiting"
		pass

	pipeline.set_state(gst.STATE_NULL)
	pipeline.get_state(gst.CLOCK_TIME_NONE)
