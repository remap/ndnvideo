#! /usr/bin/env python

import pygst
pygst.require("0.10")
import gst
import gobject

import pyccn, threading, Queue, sys

import utils, pytimecode

class CCNReceiver(pyccn.Closure):
	queue = Queue.Queue(2)
	caps = None
	frame_rate = None

	def __init__(self, uri):
		self._handle = pyccn.CCN()
		self._uri = pyccn.Name(uri)
		self._name_segments = self._uri.append('segments')
		self._name_frames = self._uri.append('frames')
		self._segment = 0
		self._seek_segment = None

	def fetch_stream_info(self):
		name = self._uri.append('stream_info')

		print "Fetching stream_info from %s ..." % name

		co = self._handle.get(name)
		if not co:
			print "Unable to fetch %s" % name
			sys.exit(10)

		self.caps = gst.caps_from_string(co.content)
		print "Stream caps: %s" % self.caps

		framerate = self.caps[0]['framerate']
		self.frame_rate = utils.framerate2str(framerate)

		return self.caps

	def fetch_seek_query(self, tc):
		interest = pyccn.Interest(childSelector=1)
		interest.exclude = pyccn.ExclusionFilter()

		exc_tc = tc + 1
		interest.exclude.add_name(pyccn.Name([exc_tc.make_timecode()]))
		interest.exclude.add_any()

		co = self._handle.get(self._name_frames, interest)
		if not co:
			raise Exception("Some bullshit exception")

		tc = pytimecode.PyTimeCode(exc_tc.framerate, start_timecode=co.name[-1])

		return tc, int(co.content)

	def seek(self, ns):
		tc = pytimecode.PyTimeCode(self.frame_rate, start_seconds=ns/float(gst.SECOND))

		print "Requesting tc: %s" % tc
		rtc, segment = self.fetch_seek_query(tc)
		print "Seeking to segment %d" % segment

		self._seek_segment = segment

	def start(self):
		self._receiver_thread = threading.Thread(target=self.run)
		self._running = True
		self._receiver_thread.start()
		self.next_interest()

	def stop(self):
		self._running = False
		self._handle.setRunTimeout(0)
		self._receiver_thread.join()

	def run(self):
		print "Running ccn loop"
		self._handle.run(-1)
		print "Finished running ccn loop"

	def next_interest(self):
		if type(self._seek_segment) is int:
			print "Switching to next segment"
			self.segbuf = []
			self._segment = self._seek_segment
			self._seek_segment = True

		name = self._name_segments.appendSegment(self._segment)
		self._segment += 1

		#print "Issuing an interest for: %s" % name
		self._handle.expressInterest(name, self)

	def upcall(self, kind, info):
		if kind == pyccn.UPCALL_FINAL:
			return pyccn.RESULT_OK

		elif kind == pyccn.UPCALL_CONTENT:
			if not hasattr(self, 'segbuf'):
				self.segbuf = []

			print "Received %s" % info.ContentObject.name

			last, content = utils.packet2buffer(info.ContentObject.content)
			self.segbuf.append(content)
			if last == 0:
				res = self.segbuf[0]
				for e in self.segbuf[1:]:
					res = res.merge(e)
				self.segbuf = []
				if self._seek_segment == True:
					print "Marking as discontinued"
					res.flag_set(gst.BUFFER_FLAG_DISCONT)
					self._seek_segment = None
				self.queue.put(res)

			self.next_interest()
			return pyccn.RESULT_OK

		elif kind == pyccn.UPCALL_INTEREST_TIMED_OUT:
			print "timeout - reexpressing"
			return pyccn.RESULT_REEXPRESS

		print "kind: %d" % kind

		return pyccn.RESULT_ERR

if __name__ == '__main__':

	gobject.threads_init()

	from src import CCNSrc

	#def on_eos(bus, msg):
	#	mainloop.quit()

	def bus_call(bus, message, loop):
		t = message.type
		if t == gst.MESSAGE_EOS:
			print("End-of-stream")
			loop.quit()
		elif t == gst.MESSAGE_ERROR:
			err, debug = message.parse_error()
			print("Error: %s: %s" % (err, debug))
			loop.quit()
		return True

#	src = gst.element_factory_make('filesrc')
#	src.set_property('location', 'test.bin')

	receiver = CCNReceiver('/videostream')
	caps = receiver.fetch_stream_info()

	src = CCNSrc('source')
	src.set_receiver(receiver)

	decoder = gst.element_factory_make('ffdec_h264')
	decoder.set_property('max-threads', 3)

	sink = gst.element_factory_make('xvimagesink')

	pipeline = gst.Pipeline()
	pipeline.add(src, decoder, sink)


	src.link_filtered(decoder, caps)
	decoder.link(sink)

	#gst.element_link_many(src, demuxer, decoder, sink)

	loop = gobject.MainLoop()
	bus = pipeline.get_bus()
	#bus.add_signal_watch()
	#bus.connect('message::eos', on_eos)
	bus.add_watch(bus_call, loop)

	pipeline.set_state(gst.STATE_PLAYING)
	print "Entering loop"

	res = pipeline.seek_simple(gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH | gst.SEEK_FLAG_ACCURATE, 90 * gst.SECOND)
	print "Seek result: %s" % res

	try:
		loop.run()
	except KeyboardInterrupt:
		print "Ctrl+C pressed, exitting"
		pass

	pipeline.set_state(gst.STATE_NULL)
	pipeline.get_state(gst.CLOCK_TIME_NONE)
