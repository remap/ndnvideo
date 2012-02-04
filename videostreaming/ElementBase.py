import math, Queue
import pyccn

import utils

class CCNPacketizer(object):
	_chunk_size = 4096
	_segment = 0
	_caps = None

	def __init__(self, publisher, uri):
		self.publisher = publisher

		self._basename = pyccn.Name(uri)
		self._name_segments = self._basename.append("segments")
		self._name_frames = self._basename.append("index")

		self._key = pyccn.CCN.getDefaultKey()
		self._signed_info = pyccn.SignedInfo(self._key.publicKeyID, pyccn.KeyLocator(self._key))
		self._signed_info_frames = pyccn.SignedInfo(self._key.publicKeyID, pyccn.KeyLocator(self._key))

	def set_caps(self, caps):
		if not self._caps:
			self._caps = caps
			packet = self.prepare_stream_info_packet(caps)
			self.publisher.put(packet)

			self.post_set_caps(caps)

	def post_set_caps(self, caps):
		pass

	def prepare_stream_info_packet(self, caps):
		name = self._basename.append("stream_info")

		co = pyccn.ContentObject(name, self._caps, self._signed_info)
		co.sign(self._key)

		return co

	def prepare_frame_packet(self, frame, segment):
		name = self._name_frames.append(frame)

		co = pyccn.ContentObject(name, segment, self._signed_info_frames)
		co.sign(self._key)

		return co

	def prepare_packet(self, segment, left, data):
		name = self._name_segments.appendSegment(segment)

		packet = utils.buffer2packet(left, data)
		co = pyccn.ContentObject(name, packet, self._signed_info)
		co.sign(self._key)

		return co

	def pre_process_buffer(self, buffer):
		pass

	def process_buffer(self, buffer):
		self.pre_process_buffer(buffer)

		chunk_size = self._chunk_size - utils.packet_hdr_len
		nochunks = int(math.ceil(buffer.size / float(chunk_size)))

		data_off = 0
		while data_off < buffer.size:
			assert(nochunks > 0)

			data_size = min(chunk_size, buffer.size - data_off)
			chunk = buffer.create_sub(data_off, data_size)
			chunk.stamp(buffer)
			data_off += data_size

			nochunks -= 1
			packet = self.prepare_packet(self._segment, nochunks, chunk)
			self._segment += 1

			self.publisher.put(packet)
		assert(nochunks == 0)

class CCNDepacketizer(pyccn.Closure):
	queue = Queue.Queue(10)
	duration_ns = None

	_running = False
	_caps = None
	_tc = None
	_seek_segment = None
	_duration_last = None
	_cmd_q = Queue.Queue(2)

	def __init__(self, uri):
		self._handle = pyccn.CCN()
		self._get_handle = pyccn.CCN()

		self._uri = pyccn.Name(uri)
		self._name_segments = self._uri + 'segments'
		self._name_frames = self._uri + 'index'

		self._pipeline = utils.PipelineFetch(10, self.issue_interest, self.process_response)

	def fetch_stream_info(self):
		name = self._uri.append('stream_info')
		debug(self, "Fetching stream_info from %s ..." % name)

		co = self._get_handle.get(name)
		if not co:
			debug(self, "Unable to fetch %s" % name)
			exit(10)

		self._caps = gst.caps_from_string(co.content)
		debug(self, "Stream caps: %s" % self._caps)

		self.post_fetch_stream_info(self._caps)

	def post_fetch_stream_info(self, caps):
		pass
		#framerate = self._caps[0]['framerate']
		#self._tc = utils.TCConverter(framerate)

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

#
# Bellow methods are called by thread
#

	def run(self):
		debug(self, "Running ccn loop")
		self.fetch_last_frame()

		iter = 0
		while self._running:
			if iter > 100:
				iter = 0
				self.fetch_last_frame()

			self._handle.run(100)
			self.process_commands()
			iter += 1

		debug(self, "Finished running ccn loop")

	def process_commands(self):
		try:
			if self._cmd_q.empty():
				return
			cmd = self._cmd_q.get_nowait()
		except Queue.Empty:
			return

		if cmd[0] == CMD_SEEK:
			tc, segment = self.fetch_seek_query(cmd[1])
			debug(self, "Seeking to segment %d [%s]" % (segment, tc))
			self._seek_segment = True
			self._upcall_segbuf = []
			self._pipeline.reset(segment)
			self._cmd_q.task_done()
		else:
			raise Exception, "Unknown command: %d" % cmd

	def fetch_seek_query(self, ns):
		tc = self._tc.ts2tc_obj(ns)

		debug(self, "Fetching segment number for %s" % tc)

		interest = pyccn.Interest(childSelector = 1, answerOriginKind = pyccn.AOK_NONE)
		interest.exclude = pyccn.ExclusionFilter()

		tc.next()
		interest.exclude.add_name(pyccn.Name([tc.make_timecode()]))
		interest.exclude.add_any()

		debug(self, "Sending interest to %s" % self._name_frames)
		debug(self, "Exclusion list %s" % interest.exclude)
		co = self._get_handle.get(self._name_frames, interest)
		if not co:
			debug(self, "No response, most likely frame 00:00:00:00 doesn't exist in the network, assuming it indicates first segment")
			return "00:00:00:00", 0
			raise IOError("Unable to fetch frame before %s" % tc)
		debug(self, "Got segment: %s" % co.content)

		tc = co.name[-1]
		segment = int(co.content)

		return tc, segment

	def fetch_last_frame(self):
		interest = pyccn.Interest(childSelector = 1)

		if self._duration_last:
			interest.exclude = pyccn.ExclusionFilter()
			interest.exclude.add_any()
			interest.exclude.add_name(pyccn.Name([self._duration_last]))

		co = self._get_handle.get(self._name_frames, interest, 100)
		if co:
			self._duration_last = co.name[-1]

		print ">%s<" % self._duration_last
		if self._duration_last:
			self.duration_ns = self._tc.tc2ts(self._duration_last)
		else:
			self.duration_ns = 0

	def issue_interest(self, segment):
		name = self._name_segments.appendSegment(segment)
		#debug(self, "Issuing an interest for: %s" % name)
		interest = pyccn.Interest(interestLifetime=1.0)
		self._handle.expressInterest(name, self, interest)

	def process_response(self, co):
		if not hasattr(self, '_upcall_segbuf'):
			self._upcall_segbuf = []

		if not co:
			self._upcall_timeout = True
			return

		last, content, timestamp, duration = utils.packet2buffer(co.content)
		#debug(self, "Received %s (left: %d)" % (co.name, last))

		self._upcall_segbuf.append(content)

		if last == 0:
			status = 0

			res = gst.Buffer(b''.join(self._upcall_segbuf))
			res.timestamp = timestamp
			res.duration = duration
			#res.caps = self._caps
			self._upcall_segbuf = []

			if hasattr(self, '_upcall_timeout') and self._upcall_timeout:
				self._upcall_timeout = False
				res.flag_set(gst.BUFFER_FLAG_DISCONT)

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

		elif kind == pyccn.UPCALL_FINAL:
			return pyccn.RESULT_OK

		elif kind == pyccn.UPCALL_CONTENT:
			self._pipeline.put(utils.seg2num(info.ContentObject.name[-1]), info.ContentObject)
			return pyccn.RESULT_OK

		elif kind == pyccn.UPCALL_INTEREST_TIMED_OUT:
			debug(self, "timeout, skipping")
			self._pipeline.put(utils.seg2num(info.Interest.name[-1]), None)
			return pyccn.RESULT_OK
			debug(self, "timeout - reexpressing")
			return pyccn.RESULT_REEXPRESS

		debug(self, "Got unknown kind: %d" % kind)

		return pyccn.RESULT_ERR

