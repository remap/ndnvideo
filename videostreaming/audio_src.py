#! /usr/bin/env python

import pygst
pygst.require("0.10")
import gst
import gobject

import Queue, traceback, threading
import pyccn

import utils

CMD_SEEK = 1

def debug(cls, text):
	print "%s: %s" % (cls.__class__.__name__, text)

class CCNAudioDepacketizer(pyccn.Closure):
	queue = Queue.Queue(1)
#	last_index = None

	_running = False
	_caps = None
	_seek_segment = None
#	_duration_last = None
	_cmd_q = Queue.Queue(2)

	def __init__(self, uri):
		self._handle = pyccn.CCN()
		self._get_handle = pyccn.CCN()

		self._uri = pyccn.Name(uri)
		self._name_segments = self._uri + 'segments'
		self._name_index = self._uri + 'index'

		self._pipeline = utils.PipelineFetch(1, self.issue_interest, self.process_response)

	def fetch_stream_info(self):
		name = self._uri.append('stream_info')
		debug(self, "Fetching stream_info from %s ..." % name)

		co = self._get_handle.get(name)
		if not co:
			debug(self, "Unable to fetch %s" % name)
			exit(10)

		self._caps = gst.caps_from_string(co.content)
		debug(self, "Stream caps: %s" % self._caps)

	def get_caps(self):
		if not self._caps:
			self.fetch_stream_info()

		return self._caps

	def start(self):
		self._receiver_thread = threading.Thread(target = self.run)
		self._running = True
		self._receiver_thread.start()

	def stop(self):
		self._running = False
		self.finish_ccn_loop()
		debug(self, "Waiting for ccn to shutdown")
		self._receiver_thread.join()
		debug(self, "Shot down")

	def finish_ccn_loop(self):
		self._handle.setRunTimeout(0)

	def seek(self, ns):
		self._cmd_q.put([CMD_SEEK, ns])
		self.finish_ccn_loop()

	def run(self):
		debug(self, "Running ccn loop")
#		self.fetch_last_frame()

#		iter = 0
		while self._running:
#			if iter > 100:
#				iter = 0
#				self.fetch_last_frame()

			self._handle.run(100)
			self.process_commands()
#			iter += 1

		debug(self, "Finished running ccn loop")

	def process_commands(self):
		try:
			if self._cmd_q.empty():
				return
			cmd = self._cmd_q.get_nowait()
		except Queue.Empty:
			return

		if cmd[0] == CMD_SEEK:
			ns, segment = self.fetch_seek_query(cmd[1])
			debug(self, "Seeking to segment %d [%s]" % (segment, ns))
			self._seek_segment = True
			self._upcall_segbuf = []
			self._pipeline.reset(segment)
			self._cmd_q.task_done()
		else:
			raise Exception, "Unknown command: %d" % cmd

	def fetch_seek_query(self, ns):
		debug(self, "Fetching segment number for %s" % ns)

		interest = pyccn.Interest(childSelector = 1, answerOriginKind = pyccn.AOK_NONE)
		interest.exclude = pyccn.ExclusionFilter()

		ns += 1
		interest.exclude.add_name(pyccn.Name([ns]))
		interest.exclude.add_any()

		#debug(self, "Sending interest to %s" % self._name_index)
		co = self._get_handle.get(self._name_index, interest)
		if not co:
			return 0, 0
			raise IOError("Unable to fetch frame before %s" % tc)
		debug(self, "Got segment: %s" % co.content)

		ns = pyccn.Name.seg2num(co.name[-1])
		segment = int(co.content)

		return ns, segment

	def issue_interest(self, segment):
		name = self._name_segments.appendSegment(segment)
		#debug(self, "Issuing an interest for: %s" % name)
		self._handle.expressInterest(name, self)

	def process_response(self, co):
		if not hasattr(self, '_upcall_segbuf'):
			self._upcall_segbuf = []

		last, content, timestamp, duration = utils.packet2buffer(co.content)
		#debug(self, "Received %s (left: %d)" % (co.name, last))

		self._upcall_segbuf.append(content)

		if last == 0:
			status = 0

			res = gst.Buffer(b''.join(self._upcall_segbuf))
			res.timestamp = timestamp
			res.duration = duration
			self._upcall_segbuf = []

			# Marking jump due to seeking
			if self._seek_segment == True:
				debug(self, "Marking as discontinued")
				status = CMD_SEEK
				self._seek_segment = None

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
			debug(self, "timeout - reexpressing")
			return pyccn.RESULT_REEXPRESS

		debug(self, "Got unknown kind: %d" % kind)

		return pyccn.RESULT_ERR

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
		debug(self, "Called do_get_caps")
		return self.depacketizer.get_caps()

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
#		print "Got event %s" % event.type
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
					debug(self, "New segment: %s" % r)

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
#		#debug(self, "Returning %s %d" % (query.parse_duration()))
#
#		return True

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
