import pygst
pygst.require("0.10")
import gst
import gobject

import math, Queue, threading, struct, traceback, time, datetime

import pyccn
import utils

__all__ = ["CCNPacketizer", "CCNDepacketizer"]

# left, offset, element count
packet_hdr = "!BHB"
packet_hdr_len = struct.calcsize(packet_hdr)

# size, timestamp, duration
segment_hdr = "!IQQ"
segment_hdr_len = struct.calcsize(segment_hdr)

CMD_SEEK = 1

def debug(cls, text):
	print "%s: %s" % (cls.__class__.__name__, text)

class DataSegmenter(object):
	def __init__(self, callback, max_size = None):
		global packet_hdr_len

		self._callback = callback
		self._max_size = None if max_size is None else max_size - packet_hdr_len

		self._packet_content = bytearray()
		self._packet_elements = 0
		self._packet_element_off = 0
		self._packet_lost = False

	@staticmethod
	def buffer2segment(buffer):
		global segment_hdr, segment_hdr_len

		return struct.pack(segment_hdr, buffer.size, buffer.timestamp, \
				buffer.duration) + buffer.data

	@staticmethod
	def segment2buffer(segment, offset):
		global segment_hdr, segment_hdr_len

		if len(segment) - offset < segment_hdr_len:
			return None, offset

		header = bytes(segment[offset:offset + segment_hdr_len])
		size, timestamp, duration = struct.unpack(segment_hdr, header)
		start = offset + segment_hdr_len
		end = offset + segment_hdr_len + size

		if end > len(segment):
			return None, offset

		buf = gst.Buffer(bytes(segment[start:end]))
		buf.timestamp, buf.duration = timestamp, duration

		return buf, end

	def process_buffer(self, buffer, start_fresh = False, flush = False):
		assert self._max_size, "You can't use process_buffer without defining max_size"

		if start_fresh and len(self._packet_content) > 0:
			self.perform_send_callback(0)

		segment = self.buffer2segment(buffer)
		self._packet_content.extend(segment)
		self._packet_elements += 1

		nochunks = int(math.ceil(len(self._packet_content) \
				/ float(self._max_size)))

		while nochunks >= 2:
			#assert(nochunks > 0)
			packet_size = min(self._max_size, len(self._packet_content))
			nochunks -= 1
			self.perform_send_callback(nochunks, packet_size)
		assert(nochunks == 1)

		if len(self._packet_content) == self._max_size or flush:
			self.perform_send_callback(0)

	def process_buffer_split(self, buffer):
		global packet_hdr

		segment = self.buffer2segment(buffer)
		segment_size = len(segment)

		nochunks = int(math.ceil(segment_size / float(self._max_size)))

		data_off = 0
		while data_off < segment_size:
			assert(nochunks > 0)

			data_size = min(self._max_size, segment_size - data_off)
			chunk = segment[data_off:data_off + data_size]
			data_off += data_size

			nochunks -= 1
			header = struct.pack(packet_hdr, nochunks, 0, 0)
			self._callback(header + chunk)
		assert(nochunks == 0)

	def packet_lost(self):
		self._packet_lost = True
		self._packet_content = bytearray()
		self._packet_elements = 0

	def process_packet(self, packet):
		global packet_hdr, packet_hdr_len

		header = packet[:packet_hdr_len]
		left, offset, count = struct.unpack(packet_hdr, header)

		if not self._packet_lost or len(self._packet_content) > 0:
			offset = 0

		offset += packet_hdr_len
		self._packet_content.extend(packet[offset:])
		self._packet_elements += count

		off = 0
		while self._packet_elements > 0:
			buf, off = self.segment2buffer(self._packet_content, off)

			if buf is None:
				break

			if self._packet_lost:
				buf.flag_set(gst.BUFFER_FLAG_DISCONT)
				self._packet_lost = False

			self._callback(buf)
			self._packet_elements -= 1
		assert (left > 0 and self._packet_elements == 1) or self._packet_elements == 0, "left = %d, packet_elements = %d" % (left, self._packet_elements)
		#assert self._packet_elements <= 1, "packet_elements %d" % self._packet_elements

		self._packet_content = self._packet_content[off:]

	def perform_send_callback(self, left, size = None):
		if size is None:
			size = len(self._packet_content)

		header = struct.pack(packet_hdr, left, self._packet_element_off, \
				self._packet_elements)

		self._callback(header + bytes(self._packet_content[:size]))
		self._packet_content = self._packet_content[size:]
		self._packet_element_off = len(self._packet_content)
		self._packet_elements = 0

class CCNPacketizer(object):
	def __init__(self, publisher, uri):
		freshness = 30 * 60

		self._chunk_size = 3900
		self._segment = 0
		self._caps = None

		self.publisher = publisher

		self._basename = pyccn.Name(uri)
		self._name_segments = self._basename.append("segments")
		self._name_frames = self._basename.append("index")
		self._name_key = self._basename.append("key")

		self._key = pyccn.CCN.getDefaultKey()
		self._signed_info = pyccn.SignedInfo(self._key.publicKeyID, pyccn.KeyLocator(self._name_key), freshness = freshness)
		self._signed_info_frames = pyccn.SignedInfo(self._key.publicKeyID, pyccn.KeyLocator(self._name_key), freshness = freshness)

		self._segmenter = DataSegmenter(self.send_data, self._chunk_size)

		signed_info = pyccn.SignedInfo(self._key.publicKeyID, pyccn.KeyLocator(self._key), freshness = freshness)
		co = pyccn.ContentObject(self._name_key, self._key.publicToDER(), signed_info)
		co.sign(self._key)
		self.publisher.put(co)

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

		# Make sure the timestamp is regenerated
		self._signed_info.ccn_data_dirty = True
		co = pyccn.ContentObject(name, self._caps, self._signed_info)
		co.sign(self._key)

		return co

	def prepare_frame_packet(self, frame, segment):
		name = self._name_frames.append(frame)

		# Make sure the timestamp is regenerated
		self._signed_info_frames.ccn_data_dirty = True
		co = pyccn.ContentObject(name, segment, self._signed_info_frames)
		co.sign(self._key)

		return co

	def send_data(self, packet):
		name = self._name_segments.appendSegment(self._segment)
		self._segment += 1

		# Make sure the timestamp is regenerated
		self._signed_info.ccn_data_dirty = True
		co = pyccn.ContentObject(name, packet, self._signed_info)
		co.sign(self._key)
		self.publisher.put(co)

	def pre_process_buffer(self, buffer):
		return True, True

	def process_buffer(self, buffer):
		result = self.pre_process_buffer(buffer)
		self._segmenter.process_buffer(buffer, start_fresh = result[0],
				flush = result[1])

class CCNDepacketizer(pyccn.Closure):
	def __init__(self, uri, interval = 0.01, timeout = 1.5, retries = 0):
		# amount of time to wait for interest response
		self.interest_lifetime = timeout

		# how many times to retry request
		self.interest_retries = retries

		# maximum number of buffers we can hold in memory waiting to be processed
		self.queue = Queue.Queue(100)

		#duration of the stream (in nanoseconds)
		self.duration_ns = None

		#
		self._running = False
		self._caps = None
		self._start_time = None
		self._seek_segment = None
		self._duration_last = None
		self._cmd_q = Queue.Queue(2)

		self._handle = pyccn.CCN()
		self._get_handle = pyccn.CCN()

		self._uri = pyccn.Name(uri)
		self._name_segments = self._uri + 'segments'
		self._name_frames = self._uri + 'index'

#		self._pipeline = utils.PipelineFetch(window, self.issue_interest,
#				self.process_response)
		self._pipeline = utils.PipelineFreqFetch(self.issue_interest,
				self.process_response, interval)
		self._segmenter = DataSegmenter(self.push_data)

		self._stats_retries = 0
		self._stats_drops = 0

		self._tmp_retry_requests = {}

		DurationChecker = type('DurationChecker', (pyccn.Closure,),
			dict(upcall = self.duration_process_result))
		self._duration_callback = DurationChecker()

		self._data_rate = None

	def fetch_stream_info(self):
		name = self._uri.append('stream_info')
		debug(self, "Fetching stream_info from %s ..." % name)

		co = self._get_handle.get(name)
		if not co:
			debug(self, "Unable to fetch %s" % name)
			exit(10)

		ts = co.signedInfo.py_timestamp
		debug(self, "Got timestamp: %s %f" % (time.ctime(ts), ts))
		self._start_time = ts

		self._caps = gst.caps_from_string(co.content)
		debug(self, "Stream caps: %s" % self._caps)

		self.post_fetch_stream_info(self._caps)

		if self._start_time is None:
			self.fetch_start_time()

	def fetch_start_time(self):
		name = self._name_segments.appendSegment(0)
		co = self._get_handle.get(name)
		if not co:
			debug(self, "Unable to fetch %s" % name)
			exit(10)

		ts = co.signedInfo.py_timestamp
		debug(self, "Got timestamp: %s %f" % (time.ctime(ts), ts))
		self._start_time = ts

	def post_fetch_stream_info(self, caps):
		pass

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
		debug(self, "Waiting for ccn to shutdown ...")
		self._receiver_thread.join()
		debug(self, "Thread was shut down.")

	def finish_ccn_loop(self):
		self._handle.setRunTimeout(0)

	def seek(self, ns):
		self._cmd_q.put([CMD_SEEK, ns])
		self.finish_ccn_loop()

	def __check_duration(self, interest):
		t_start = time.time()
		co = self._get_handle.get(self._name_frames, interest)
		t_end = time.time()

		if co is None:
			return None

		name = co.name[-1:]
		duration = pyccn.Name.seg2num(co.name[-1])
		t_packet = co.signedInfo.py_timestamp
		rtt = t_end - t_start
		t_diff = t_start - t_packet

		print "Duration:", datetime.timedelta(seconds = duration / float(gst.SECOND))
		print "Packet timestamp:", time.ctime(t_packet)
		print "Time difference:", datetime.timedelta(seconds = t_diff)
		print "Rtt:", rtt

		return duration, t_packet, t_diff, rtt, name

	def check_duration_initial(self):
		duration = None

		interest = pyccn.Interest(childSelector = 1,
			answerOriginKind = pyccn.AOK_DEFAULT)

		exclude = interest.exclude = pyccn.ExclusionFilter()

		while True:
			res = self.__check_duration(interest)
			if res is None:
				break

			duration, t_packet, t_diff, rtt, name = res

			print "Excluding %r" % name
			exclude.reset()
			exclude.add_any()
			exclude.add_name(name)

		return duration

#
# Bellow methods are called by thread
#

	def run(self):
		debug(self, "Running ccn loop")

		while self._running:
			self.check_duration()
			self._handle.run(10000)
			self.process_commands()

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
			self._segmenter.packet_lost()
			self._pipeline.reset(segment)
			self._cmd_q.task_done()
		else:
			raise Exception, "Unknown command: %d" % cmd

	def fetch_seek_query(self, ns):
		index = self.ts2index_add_1(ns)

		#debug(self, "Fetching segment number before %s" % index)

		interest = pyccn.Interest(childSelector = 1,
			answerOriginKind = pyccn.AOK_NONE)
		interest.exclude = pyccn.ExclusionFilter()
		interest.exclude.add_name(pyccn.Name([index]))
		interest.exclude.add_any()

		#debug(self, "Sending interest to %s" % self._name_frames)
		#debug(self, "Exclusion list %s" % interest.exclude)
		while True:
			co = self._get_handle.get(self._name_frames, interest)
			if co:
				break
			debug(self, "Timeout while seeking %d, retrying ..." % (ns))
		debug(self, "Got segment: %s" % co.content)

		index = co.name[-1]
		segment = int(co.content)

		return (self.index2ts(index), segment)

	def duration_process_result(self, kind, info):
		if kind == pyccn.UPCALL_FINAL:
			return pyccn.RESULT_OK

		if kind == pyccn.UPCALL_CONTENT_UNVERIFIED:
			return pyccn.RESULT_VERIFY

		if kind != pyccn.UPCALL_CONTENT and kind != pyccn.UPCALL_INTEREST_TIMED_OUT:
			return pyccn.RESULT_ERR

		if kind == pyccn.UPCALL_CONTENT:
			self._duration_last = info.ContentObject.name[-1]
		else:
			debug(self, "No response received for duration request")

		if self._duration_last:
			self.duration_ns = self.index2ts(self._duration_last)
		else:
			self.duration_ns = 0

		return pyccn.RESULT_OK

	def check_duration(self):
		interest = pyccn.Interest(childSelector = 1)

		if self._duration_last:
			interest.exclude = pyccn.ExclusionFilter()
			interest.exclude.add_any()
			interest.exclude.add_name(pyccn.Name([self._duration_last]))

		self._handle.expressInterest(self._name_frames, self._duration_callback, interest)

	def issue_interest(self, segment):
		name = self._name_segments.appendSegment(segment)

		#debug(self, "Issuing an interest for: %s" % name)
		self._tmp_retry_requests[str(name[-1])] = self.interest_retries

		interest = pyccn.Interest(interestLifetime = self.interest_lifetime)
		self._handle.expressInterest(name, self, interest)

		return True

	def process_response(self, co):
		if not co:
#			if self._data_rate:
#				self._data_rate[3] += 1
			self._data_rate = None

			self._segmenter.packet_lost()
			return

		n_ts = time.time()
		n_cts = co.signedInfo.py_timestamp
		n_diff = n_ts - n_cts

		if self._data_rate:
			o_interval, o_ts, o_cts, o_segments = self._data_rate
			o_diff = o_ts - o_cts

			interval_diff = n_diff - o_diff
			n_interval = self._pipeline.interval - interval_diff / o_segments
			n_interval = max(0, min(10, n_interval))
			diff = n_interval - o_interval
			n_interval = o_interval + 0.0625 * diff

			debug(self, "interval %f diff %f" % (n_interval, interval_diff))

			self._pipeline.interval = n_interval

		self._data_rate = [self._pipeline.interval, n_ts, n_cts, 1]

		self._segmenter.process_packet(co.content)

	def push_data(self, buf):
		status = 0

		# Marking jump due to seeking
		if self._seek_segment == True:
			debug(self, "Marking as discontinued")
			status = CMD_SEEK
			self._seek_segment = None

		while True:
			try:
				self.queue.put((status, buf), True, 1)
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
			self._pipeline.put(pyccn.Name.seg2num(info.ContentObject.name[-1]),
							info.ContentObject)
			return pyccn.RESULT_OK

		elif kind == pyccn.UPCALL_INTEREST_TIMED_OUT:
			name = str(info.Interest.name[-1])

			if self._tmp_retry_requests[name]:
#				debug(self, "timeout for %s - re-expressing" % info.Interest.name)
				self._stats_retries += 1
				self._tmp_retry_requests[name] -= 1
				return pyccn.RESULT_REEXPRESS

#			debug(self, "timeout for %r - skipping" % info.Interest.name)
			self._stats_drops += 1
			del self._tmp_retry_requests[name]
			self._pipeline.timeout(pyccn.Name.seg2num(info.Interest.name[-1]))
			return pyccn.RESULT_OK

		elif kind == pyccn.UPCALL_CONTENT_UNVERIFIED:
			debug(self, "%s arrived unverified, fetching the key" % info.ContentObject.name)
			return pyccn.RESULT_VERIFY

		debug(self, "Got unknown kind: %d" % kind)

		return pyccn.RESULT_ERR

	def get_status(self):
		return "Pipeline size: %d interval: %f (%d) Position: %d Retries: %d" \
			" Drops: %d Duration: %ds" \
			% (self._pipeline.pipeline_size, self._pipeline.interval, self._pipeline.is_running(),
			self._pipeline.position, self._stats_retries, self._stats_drops,
			self.duration_ns / gst.SECOND if self.duration_ns else -1.0)

	def ts2index(self, ts):
		return pyccn.Name.num2seg(ts)

	def ts2index_add_1(self, ts):
		return self.ts2index(ts + 1)

	def index2ts(self, index):
		return pyccn.Name.seg2num(index)

class CCNElementSrc(gst.BaseSrc):
	__gsttemplates__ = (
		gst.PadTemplate("src",
			gst.PAD_SRC,
			gst.PAD_ALWAYS,
			gst.caps_new_any()),
		)

	def __init__(self):
		gst.BaseSrc.__init__(self)
		self.depacketizer = None
		self.set_format(gst.FORMAT_TIME)
		self.seek_in_progress = None
		self._no_locking = False

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
		self.depacketizer.seek(segment.start)
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

	def query_duration(self):
		debug(self, "Querying duration")
		return self.depacketizer.check_duration_initial()

	def get_status(self):
		return self.depacketizer.get_status()

#	def do_change_state(self, transition):
#		print "CHANGE IS INEVITABLE!"
#		print transition
#		res = gst.BaseSrc.do_change_state(self, transition)
#		print res
#		return gst.STATE_CHANGE_SUCCESS
