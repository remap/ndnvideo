#! /usr/bin/env python

import pygst
pygst.require("0.10")
import gst
import gobject

import Queue, traceback, threading
import pyccn

import utils

CMD_SEEK = 1

def debug(text):
	print "CCNReceiver: %s" % text

class CCNAudioDepacketizer(pyccn.Closure):
	queue = Queue.Queue(1)
	caps = None
#	last_index = None

#	_cmd_q = Queue.Queue(2)
#	_running = False
#	_seek_segment = None
#	_duration_last = None

	def __init__(self, uri):
		self._handle = pyccn.CCN()
		self._get_handle = pyccn.CCN()

		self._uri = pyccn.Name(uri)
		self._name_segments = self._uri.append('segments')
		self._name_index = self._uri.append('index')
		self._pipeline = utils.PipelineFetch(1, self.issue_interest, self.process_response)

	def fetch_stream_info(self):
		name = self._uri.append('stream_info')
		debug("Fetching stream_info from %s ..." % name)

		co = self._get_handle.get(name)
		if not co:
			debug("Unable to fetch %s" % name)
			sys.exit(10)

		self.caps = gst.caps_from_string(co.content)
		debug("Stream caps: %s" % self.caps)

	def get_caps(self):
		if not self.caps:
			self.fetch_stream_info()

		return self.caps

	def start(self):
		self._receiver_thread = threading.Thread(target=self.run)
		self._running = True
		self._receiver_thread.start()

	def stop(self):
		self._running = False
		self.finish_ccn_loop()
		debug("Waiting for ccn to shutdown")
		self._receiver_thread.join()
		debug("Shot down")

	def finish_ccn_loop(self):
		self._handle.setRunTimeout(0)

#	def seek(self, ns):
#		self._cmd_q.put([CMD_SEEK, ns])
#		self.finish_ccn_loop()

	def run(self):
		debug("Running ccn loop")
		self._pipeline.reset(0)
#		self.fetch_last_frame()

#		iter = 0
		while self._running:
#			if iter > 100:
#				iter = 0
#				self.fetch_last_frame()

			self._handle.run(100)
#			self.process_commands()
#			iter += 1

		debug("Finished running ccn loop")

#	def process_commands(self):
#		try:
#			if self._cmd_q.empty():
#				return
#			cmd = self._cmd_q.get_nowait()
#		except Queue.Empty:
#			return
#
#		if cmd[0] == CMD_SEEK:
#			tc, segment = self.fetch_seek_query(cmd[1])
#			debug("Seeking to segment %d [%s]" % (segment, tc))
#			self._seek_segment = True
#			self._upcall_segbuf = []
#			self._pipeline.reset(segment)
#			self._cmd_q.task_done()
#		else:
#			raise Exception, "Unknown command: %d" % cmd
#
#	def fetch_seek_query(self, ns):
#		tc = self._tc.ts2tc_obj(ns)
#
#		debug("Fetching segment number for %s" % tc)
#
#		interest = pyccn.Interest(childSelector = 1)
#		interest.exclude = pyccn.ExclusionFilter()
#
#		tc.next()
#		interest.exclude.add_name(pyccn.Name([tc.make_timecode()]))
#		interest.exclude.add_any()
#
#		#debug("Sending interest to %s" % self._name_index)
#		co = self._get_handle.get(self._name_index, interest)
#		if not co:
#			return "00:00:00:00", 0
#			raise IOError("Unable to fetch frame before %s" % tc)
#		debug("Got segment: %s" % co.content)
#
#		tc = co.name[-1]
#		segment = int(co.content)
#
#		return tc, segment

	def issue_interest(self, segment):
		name = self._name_segments.appendSegment(segment)
		#debug("Issuing an interest for: %s" % name)
		self._handle.expressInterest(name, self)

	def process_response(self, co):
		if not hasattr(self, '_upcall_segbuf'):
			self._upcall_segbuf = []

		last, content, timestamp, duration = utils.packet2buffer(co.content)
		#debug("Received %s (left: %d)" % (co.name, last))

		self._upcall_segbuf.append(content)

		if last == 0:
			status = 0

			res = gst.Buffer(b''.join(self._upcall_segbuf))
			res.timestamp = timestamp
			res.duration = duration
			#res.caps = self.caps
			self._upcall_segbuf = []

#			# Marking jump due to seeking
#			if self._seek_segment == True:
#				debug("Marking as discontinued")
#				status = CMD_SEEK
#				self._seek_segment = None

			while True:
				try:
					self.queue.put((status, res), True, 1)
					break
				except Queue.Full:
					if not self._running:
						break

	def upcall(self, kind, info):
		if not self._running:
			return pyccn.RESULT_OK

		if kind == pyccn.UPCALL_FINAL:
			return pyccn.RESULT_OK

		elif kind == pyccn.UPCALL_CONTENT:
			self._pipeline.put(utils.seg2num(info.ContentObject.name[-1]), info.ContentObject)
			return pyccn.RESULT_OK

		elif kind == pyccn.UPCALL_INTEREST_TIMED_OUT:
			debug("timeout - reexpressing")
			return pyccn.RESULT_REEXPRESS

		debug("Got unknown kind: %d" % kind)

		return pyccn.RESULT_ERR

def vdebug(text):
	print "CCNSrc: %s" % text

class AudioSrc(gst.BaseSrc):
	__gtype_name__ = 'AudioSrc'
	__gstdetails__ = ("CCN Audio Source", "Source/Network",
		"Receives audio data over a CCNx network", "Derek Kulinski <takeda@takeda.tk>")

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

	depacketizer = None

	def __init__(self):
		gst.BaseSrc.__init__(self)
		self.set_format(gst.FORMAT_TIME)
		self.seek_in_progress = None
		self._no_locking = False

	def do_set_property(self, property, value):
		if property.name == 'location':
			self.depacketizer = CCNAudioDepacketizer(value)
		else:
			raise AttributeError, 'unknown property %s' % property.name

	def do_get_caps(self):
		vdebug("Called do_get_caps")
		return self.depacketizer.get_caps()

	def do_start(self):
		vdebug("Called start")
#		self.iff = open("caps.data", "r")
		self.depacketizer.start()
		return True

	def do_stop(self):
		vdebug("Called stop")
#		self.iff.close()
		self.depacketizer.stop()
		return True

	def do_is_seekable(self):
		vdebug("is seekable")
		return False

#	def do_event(self, event):
#		print "Got event %s" % event.type
#		return gst.BaseSrc.do_event(self, event)

	def do_create(self, offset, size):
		if self._no_locking:
			return gst.FLOW_WRONG_STATE, None

		#vdebug("Offset: %d, Size: %d" % (offset, size))
		try:
			while True:
				try:
					status, buffer = self.depacketizer.queue.get(True, 1)
#					caps = self.iff.readline().rstrip('\n')
#					c = gst.Caps(caps)
#					buffer.caps = c
					#print "%d %d %d %s" % (buffer.timestamp, buffer.duration, buffer.flags, buffer.caps)
				except Queue.Empty:
					if self._no_locking:
						return gst.FLOW_WRONG_STATE, None
					else:
						vdebug("Starving for data")
						continue

				if self._no_locking:
					self.depacketizer.queue.task_done()
					return gst.FLOW_WRONG_STATE, None

				if self.seek_in_progress is not None:
					if status != CMD_SEEK:
						vdebug("Skipping prefetched junk ...")
						self.depacketizer.queue.task_done()
						continue

					vdebug("Pushing seek'd buffer")
					event = gst.event_new_new_segment(False, 1.0, gst.FORMAT_TIME,
					                                  self.seek_in_progress, -1,
					                                  self.seek_in_progress)
					r = self.get_static_pad("src").push_event(event)
					vdebug("New segment: %s" % r)

					self.seek_in_progress = None
					buffer.flag_set(gst.BUFFER_FLAG_DISCONT)

				self.depacketizer.queue.task_done()
				return gst.FLOW_OK, buffer
		except:
			traceback.print_exc()
			return gst.FLOW_ERROR, None

#	def do_do_seek(self, segment):
#		vdebug("Asked to seek to %d" % segment.start)
#		self.seek_in_progress = segment.start
#		pos = self.depacketizer.seek(segment.start)
#		return True

#	def do_query(self, query):
#		if query.type != gst.QUERY_DURATION:
#			return gst.BaseSrc.do_query(self, query)
#
#		duration = self.depacketizer.last_frame
#
#		if not duration:
#			return True
#
#		duration = long(duration.hrs * 3600 + duration.mins * 60 + duration.secs) * gst.SECOND
#		query.set_duration(gst.FORMAT_TIME, duration)
#
#		#vdebug("Returning %s %d" % (query.parse_duration()))
#
#		return True

	def do_check_get_range(self):
		vdebug("get range")
		return False

	def do_unlock(self):
		vdebug("Unlock!!!")
		self._no_locking = True
		return True

	def do_unlock_stop(self):
		vdebug("Stop unlocking!!!")
		self._no_locking = False
		return True

gst.element_register(AudioSrc, 'AudioSrc')

if __name__ == '__main__':
	import sys

	gobject.threads_init()

	if len(sys.argv) != 2:
		print "Usage: %s <URI>" % sys.argv[0]
		exit(1)

	uri = sys.argv[1]

	pipeline = gst.parse_launch('ffdec_aac name=decoder ! autoaudiosink')

	decoder = pipeline.get_by_name("decoder")
	src = gst.element_factory_make("AudioSrc")
	src.set_property('location', uri)

	pipeline.add(src)
	src.link(decoder)

	loop = gobject.MainLoop()

	pipeline.set_state(gst.STATE_PLAYING)
	print "Entering loop"

	try:
		loop.run()
	except KeyboardInterrupt:
		print "Ctrl+C pressed, exitting"
		pass

	pipeline.set_state(gst.STATE_NULL)
	pipeline.get_state(gst.CLOCK_TIME_NONE)
