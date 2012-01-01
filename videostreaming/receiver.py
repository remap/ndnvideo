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

	_cmd_q = Queue.Queue(2)
	_running = False
	_segment = 0
	_seek_segment = None

	def __init__(self, uri):
		self._handle = pyccn.CCN()
		self._uri = pyccn.Name(uri)
		self._name_segments = self._uri.append('segments')
		self._name_frames = self._uri.append('frames')

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
		print "Fetching segment number for %s" % tc
		interest = pyccn.Interest(childSelector=1)
		interest.exclude = pyccn.ExclusionFilter()

		exc_tc = tc + 1
		interest.exclude.add_name(pyccn.Name([exc_tc.make_timecode()]))
		interest.exclude.add_any()

		co = self._handle.get(self._name_frames, interest)
		#co = utils.safe_get(self._handle, self._name_frames, interest)
		if not co:
			raise Exception("Some bullshit exception")

		tc = pytimecode.PyTimeCode(exc_tc.framerate, start_timecode=co.name[-1])
		segment = int(co.content)
		print "Got segment: %s" % segment

		return tc, segment

	def fetch_last_frame(self):
		interest = pyccn.Interest(childSelector=1)

		co = self._handle.get(self._name_frames, interest)
		if not co:
			raise Exception("Some bullshit exception")

		tc = pytimecode.PyTimeCode(exc_tc.framerate, start_timecode=co.name[-1])

		return tc

	def process_commands(self):
		if self._cmd_q.empty():
			return

		try:
			cmd = self._cmd_q.get_nowait()
			if cmd[0] == 1:
				tc, segment = self.fetch_seek_query(cmd[1])
				print "Seeking to segment %d [%s]" % (segment, tc)
				self._seek_segment = segment
				self._cmd_q.task_done()

				self.next_interest() # why this is necessary? Why I never get a callback?
			else:
				raise Exception, "Unknown command: %d" % cmd
		except Queue.Empty:
			return

	def seek(self, ns):
		tc = pytimecode.PyTimeCode(self.frame_rate, start_seconds=ns/float(gst.SECOND))

		print "Requesting tc: %s" % tc
		self._cmd_q.put([1, tc])
		print "Seek comand queued"

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
		while self._running:
			self._handle.run(100)
			self.process_commands()

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
			self.next_interest()
			return pyccn.RESULT_OK

		elif kind == pyccn.UPCALL_CONTENT:
			if not hasattr(self, 'segbuf'):
				self.segbuf = []

			print "Received %s" % info.ContentObject.name

			last, content = utils.packet2buffer(info.ContentObject.content)
			self.segbuf.append(content)
			if last == 0:
				#Merging, maybe I shouldn't do this :/
				res = self.segbuf[0]
				for e in self.segbuf[1:]:
					res = res.merge(e)
				self.segbuf = []

				# Marking jump due to seeking
				if self._seek_segment == True:
					print "Marking as discontinued"
					res.flag_set(gst.BUFFER_FLAG_DISCONT)
					self._seek_segment = None

				#print "before put"
				self.queue.put(res)
				#print "after put"

			#self.next_interest()
			return pyccn.RESULT_OK

		elif kind == pyccn.UPCALL_INTEREST_TIMED_OUT:
			print "timeout - reexpressing"
			return pyccn.RESULT_REEXPRESS

		print "Got unknown kind: %d" % kind

		return pyccn.RESULT_ERR

if __name__ == '__main__':
	import time

	def consumer(receiver):
		while True:
			data = receiver.queue.get()
			time.sleep(.01)

	def do_seek(receiver, sec):
		ns = int(sec * 1000 * 1000 * 1000)
		receiver.seek(ns)

	receiver = CCNReceiver('/videostream')
	receiver.fetch_stream_info()

	thread = threading.Thread(target=consumer, args=[receiver])
	thread.start()

	timer = threading.Timer(2, do_seek, args=[receiver, 30])
	timer.start()

	timer = threading.Timer(5, do_seek, args=[receiver, 0])
	timer.start()

	timer = threading.Timer(6, do_seek, args=[receiver, 0])
	timer.start()

	receiver.start()
