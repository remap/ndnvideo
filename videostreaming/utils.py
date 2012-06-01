import pygst
pygst.require('0.10')
import gst

import struct, time, Queue, bisect, threading, math, os, platform, random, socket
from operator import itemgetter
import pyccn
from pyccn import _pyccn
from pytimecode import PyTimeCode

if platform.system() == "Darwin":
	audio_sink = "audioconvert ! osxaudiosink"
	video_sink = "colorspace ! ximagesink"
else:
	audio_sink = "autoaudiosink"
	video_sink = "xvimagesink"

def read_file(fname):
	f = open(fname, "rb")
	data = f.read()
	f.close()

	return data

def packet(name, data, key):
	co = pyccn.ContentObject()
	co.name = pyccn.Name(name)
	co.content = data
	co.signedInfo.publisherPublicKeyDigest = key.publicKeyID
	co.signedInfo.keyLocator = pyccn.KeyLocator(key)
	co.sign(key)
	return co

def signed(val):
	return struct.unpack("=q", struct.pack("=Q", long(val)))[0]

def framerate2str(framerate):
	if framerate.num == 30 and framerate.denom == 1:
		fr_str = "30"
	elif framerate.num == 30000 and framerate.denom == 1001:
		fr_str = "29.97"
	elif framerate.num == 25 and framerate.denom == 1:
		fr_str = "25"
	elif framerate.num == 24000 and framerate.denom == 1001:
		fr_str = "23.98"
	else:
		raise ValueError("Unsupported framerate: %s" % framerate)

	return fr_str

class RepoPublisher(pyccn.Closure):
	def __init__(self, handle, prefix, repo_loc = None):
		self._sequence = 0;

		self.handle = handle

		if not repo_loc:
			if not os.environ.has_key('CCNR_DIRECTORY'):
				raise Exception("CCNR_DIRECTORY not defined and no repo location specified")

			dir = os.environ['CCNR_DIRECTORY']
			dir = os.path.expanduser(dir)
			repo_loc = os.path.expandvars(dir)

		self.import_loc = os.path.join(repo_loc, "import")
		self.prefix = "%s_%d_%d_" % (prefix, os.getpid(), random.randrange(2 ** 64))

		self.name = "/%C1.R.af~"
		self.interest_tpl = pyccn.Interest(scope = 1)

	def put(self, content):
		name = self.prefix + str(self._sequence)
		self._sequence += 1

		of = open(os.path.join(self.import_loc, name), "wb")
		of.write(_pyccn.dump_charbuf(content.ccn_data))
		of.close()

		self.handle.expressInterest(pyccn.Name(self.name + name), self, self.interest_tpl)
		self.handle.run(0)

	def upcall(self, kind, info):
		return pyccn.RESULT_OK

class RepoSocketPublisher(pyccn.Closure):
	def __init__(self, repo_port = None):
		if not repo_port:
			if not os.environ.has_key('CCNR_STATUS_PORT'):
				raise Exception("CCNR_STATUS_PORT not defined and no repo port specified")

			repo_port = os.environ['CCNR_STATUS_PORT']

		self.repo_dest = ('127.0.0.1', int(repo_port))

		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.sock.connect(self.repo_dest)

	def put(self, content):
		self.sock.send(_pyccn.dump_charbuf(content.ccn_data))
#		self.sock.flush()

class RingBuffer:
	def __init__(self, size):
		self.data = [None for i in xrange(size)]

	def append(self, x):
		self.data.pop(0)
		self.data.append(x)

	def get(self):
		return self.data

class CCNBuffer(Queue.Queue):
	def _init(self, maxsize):
		self.queue = []

	def _qsize(self):
		return len(self.queue)

	def _get(self):
		raise NotImplementedError()

	def _put(self, item):
		if not isinstance(item, pyccn.ContentObject):
			raise ValueError("Item needs to be of ContentObject type")

#		if self._qsize() >= self.maxsize:
#			self._get_old(10)

#		if item in self.queue:
#			raise ValueError("Item %s is already in the buffer" % item)
#		item_name = pyccn.Name(item.name)
#		name = str(item_name)
		self.queue.append((time.time(), item))

		if self._qsize() >= self.maxsize:
			return self.queue.pop(0)[1]

		return None

	def _get_element(self, interest):
		#self.queue.sort(key=itemgetter(1))

		for co in enumerate(self.queue):
			if co[1][1].matchesInterest(interest):
				return self.queue.pop(co[0])[1]

		return None

		for co in enumerate(self.queue):
			print "%d %s" % (co[0], co[1][1].name)

		raise ValueError("Element '%s' not found in the queue" % interest.name)

	def _get_old(self, diff):
		now = time.time()
		then = now - diff

		ret, new = [], []
		for co in self.queue:
			if co[0] < then:
				ret.append(co[1])
			else:
				new.append(co)

		self.queue = new

		return ret

	def put(self, item, block = True, timeout = None):
		"""Put an item into the queue.

		If optional args 'block' is true and 'timeout' is None (the default),
		block if necessary until a free slot is available. If 'timeout' is
		a positive number, it blocks at most 'timeout' seconds and raises
		the Full exception if no free slot was available within that time.
		Otherwise ('block' is false), put an item on the queue if a free slot
		is immediately available, else raise the Full exception ('timeout'
		is ignored in that case).
		"""
		self.not_full.acquire()
		try:
			if self.maxsize > 0:
				if not block:
					if self._qsize() == self.maxsize:
						raise Queue.Full
				elif timeout is None:
					while self._qsize() == self.maxsize:
						self.not_full.wait()
				elif timeout < 0:
					raise ValueError("'timeout' must be a positive number")
				else:
					endtime = time.time() + timeout
					while self._qsize() == self.maxsize:
						remaining = endtime - time.time()
						if remaining <= 0.0:
							raise Queue.Full
						self.not_full.wait(remaining)
			val = self._put(item)
			self.unfinished_tasks += 1
			self.not_empty.notify()
			return val
		finally:
			self.not_full.release()

	def get_element(self, interest, block = True, timeout = None):
		"""Remove and return an item from the queue.

		If optional args 'block' is true and 'timeout' is None (the default),
		block if necessary until an item is available. If 'timeout' is
		a positive number, it blocks at most 'timeout' seconds and raises
		the Empty exception if no item was available within that time.
		Otherwise ('block' is false), return an item if one is immediately
		available, else raise the Empty exception ('timeout' is ignored
		in that case).
		"""
		self.not_empty.acquire()
		try:
			if not block:
				if not self._qsize():
					raise Queue.Empty
			elif timeout is None:
				while not self._qsize():
					self.not_empty.wait()
			elif timeout < 0:
				raise ValueError("'timeout' must be a positive number")
			else:
				endtime = time.time() + timeout
				while not self._qsize():
					remaining = endtime - time.time()
					if remaining <= 0.0:
						raise Queue.Empty
					self.not_empty.wait(remaining)
			item = self._get_element(interest)
			self.not_full.notify()
			return item
		finally:
			self.not_empty.release()

class Interest:
	def __init__(self, i):
		self.interest = i
		self.name = i.name
		self.namelen = len(self.name)

	def __lt__(self, other):
		return self.namelen >= other

	def get(self):
		return self.interest

class InterestTable:
	interests = []

	def __init__(self):
		self.mutex = threading.Lock()

	def add(self, interest):
		self.mutex.acquire()
		try:
			bisect.insort(self.interests, Interest(interest))
		finally:
			self.mutex.release()

	def removeMatch(self, co):
		self.mutex.acquire()
		try:
			for i in enumerate(self.interests):
				inter = i[1].get()
				if co.matchesInterest(inter):
					self.interests.pop(i[0])
					return inter

			return None
		finally:
			self.mutex.release()

class FlowController(pyccn.Closure):
	queue = CCNBuffer(100)
	unmatched_interests = InterestTable()

	def __init__(self, prefix, handle):
		self.prefix = pyccn.Name(prefix)
		self.handle = handle

		self.cleanup_time = 15 * 60 # keep responses for 15 min
		handle.setInterestFilter(self.prefix, self)

	def put(self, co):
		if self.unmatched_interests.removeMatch(co):
			print "Interest already issued"
			self.handle.put(co)
			return

		co = self.queue.put(co)
		if co:
			#print "Overflow; pushing: %s" % co.name
			self.handle.put(co)

	def upcall(self, kind, info):
		if kind in [pyccn.UPCALL_FINAL, pyccn.UPCALL_CONSUMED_INTEREST]:
			return pyccn.RESULT_OK

		if kind != pyccn.UPCALL_INTEREST:
			print("Got weird upcall kind: %d" % kind)
			return pyccn.RESULT_ERR

#		answer_kind = info.Interest.get_aok_value()
#		print "answer_kind %d" % answer_kind
#		if (answer_kind & pyccn.AOK_NEW) == 0:
#			return pyccn.RESULT_OK

		try:
			co = self.queue.get_element(info.Interest, timeout = 0.2)
		except Queue.Empty:
			co = None

		if not co:
			print "Interest not queued, remembering..."
			self.unmatched_interests.add(info.Interest)
			return pyccn.RESULT_INTEREST_CONSUMED

		print "serving %s" % co.name
		self.handle.put(co)
		self.queue.task_done()

		return pyccn.RESULT_INTEREST_CONSUMED

class VersionedPull(pyccn.Closure):
	def __init__(self, base_name, callback, handle = None, version = None, latest = True):
		if not handle:
			handle = pyccn.CCN()

		# some constants
		self.version_marker = '\xfd'
		self.first_version_marker = self.version_marker
		self.last_version_marker = '\xfe\x00\x00\x00\x00\x00\x00'

		self.base_name = pyccn.Name(base_name)
		self.callback = callback
		self.handle = handle
		self.latest_version = version if version else self.first_version_marker
		self.start_with_latest = latest

	def build_interest(self, latest):
		if self.start_with_latest:
			latest = True
			self.start_with_latest = False

		excl = pyccn.ExclusionFilter()
		excl.add_any()
		excl.add_name(pyccn.Name([self.latest_version]))
		# expected result should be between those two names
		excl.add_name(pyccn.Name([self.last_version_marker]))
		excl.add_any()

		interest = pyccn.Interest(name = self.base_name, exclude = excl, \
			minSuffixComponents = 3, maxSuffixComponents = 3)
		interest.childSelector = 1 if latest else 0
		return interest

	def fetchNext(self, latest = False):
		interest = self.build_interest(latest)
		co = self.handle.get(interest.name, interest)

		if co:
			base_len = len(self.base_name)
			self.latest_version = co.name[base_len]

		return co

	def requestNext(self, latest = False):
		interest = self.build_interest(latest)
		self.handle.expressInterest(interest.name, self, interest)

	def upcall(self, kind, info):
		if kind == pyccn.UPCALL_FINAL:
			return pyccn.RESULT_OK

		# update version
		if kind in [pyccn.UPCALL_CONTENT, pyccn.UPCALL_CONTENT_UNVERIFIED]:
			base_len = len(self.base_name)
			self.latest_version = info.ContentObject.name[base_len]

		self.callback(kind, info)

		return pyccn.RESULT_OK

class PipelineFetch(object):
	increase_every = 10

	def __init__(self, window, request_cb, receive_cb):
		self.window = window
		self.request_cb = request_cb
		self.receive_cb = receive_cb

	def reset(self, position = 0):
		"""resets pipeline to specified segment and (re)starts pipelining"""

		self._buf = {}
		self._position = position
		self._requested = position - 1
		self._counter = 0

		self._request_more_data()

	def put(self, number, data):
		"""places received data packet in the buffer"""

		if number < self._position:
			print "%d < %d - dropping" % (number, self._position)
		else:
			self._buf[str(number)] = data
		self._push_out_data()

	def timeout(self, number):
		"""signals pipeline to skip given packet and move to next one"""

		self.put(number, None)

	def get_position(self):
		if not hasattr(self, '_position'):
			return -1

		return self._position

	def get_pipeline_size(self):
		"""returns current number of elements in pipeline"""

		if not hasattr(self, '_position'):
			return 0

		return self._requested - self._position + 1

	def _request_more_data(self):
		interests_left = 2 if self._counter == 0 else 1
		self._counter = (self._counter + 1) % self.increase_every

		stop = self._position + self.window - 1
		while self._requested < stop and interests_left > 0:
			self._requested += 1
			interests_left -= 1
			if not self.request_cb(self._requested):
				return
		#print "Pipeline size: %d" % (self._requested - self._position)

	def _push_out_data(self):
		while self._buf.has_key(str(self._position)):
			data = self._buf[str(self._position)]
			self.receive_cb(data)

			del self._buf[str(self._position)]
			self._position += 1

		self._request_more_data()

class TCConverter:
	"""timestamp <--> timecode conversion class"""
	def __init__(self, framerate):
		self.fr = framerate
		if framerate.num == 30 and framerate.denom == 1:
			self.fr_str = "30"
			self.df = False
		elif framerate.num == 30000 and framerate.denom == 1001:
			self.fr_str = "29.97"
			self.df = True
		elif framerate.num == 25 and framerate.denom == 1:
			self.fr_str = "25"
			self.df = False
		elif framerate.num == 24000 and framerate.denom == 1001:
			self.fr_str = "23.98"
			self.df = False # Seems like it is non drop frame
		else:
			raise ValueError("Unsupported framerate: %s" % framerate)

	def ts2frame(self, ts):
		"""Converts timestamp to a frame number"""
		return long(round(gst.Fraction(ts, gst.SECOND) * self.fr))

	def frame2ts(self, frame):
		"""Converts frame number to a timestamp"""
		return long(round(frame / self.fr * gst.SECOND))

	def ts2tc_obj(self, ts):
		"""Generate TimeCode object from a timestamp"""
		return PyTimeCode(self.fr_str, frames = self.ts2frame(ts), drop_frame = self.df)

	def tc2tc_obj(self, tc):
		"""Generate TimeCode object from a timecode string"""
		return PyTimeCode(self.fr_str, start_timecode = tc, drop_frame = self.df)

	def ts2tc(self, ts):
		"""Convert timestamp to a timecode string"""
		return self.ts2tc_obj(ts).make_timecode()

	def tc2ts(self, tc):
		"""Convert timecode (object or string) into a timestamp"""
		if type(tc) is PyTimeCode:
			t = tc
		else:
			t = self.tc2tc_obj(tc)
		return self.frame2ts(t.frames)

if __name__ == '__main__':
	def make_content(name):
		global key

		co = pyccn.ContentObject()
		co.name = pyccn.Name(name)
		co.signedInfo.publisherPublicKeyDigest = key.publicKeyID
		co.sign(key)
		return co

	def make_interest(name):
		return Interest.Interest(name = pyccn.Name(name))

	key = pyccn.CCN.getDefaultKey()

	buf = CCNBuffer()
	co0 = make_content('/a/0')
	buf.put(co0)
	co1 = make_content('/a/1')
	buf.put(co1)
	co2 = make_content('/a/2')
	buf.put(co1)

	cr1 = buf.get_element(make_interest('/a/1'))
	assert cr1 == co1
	cr0 = buf.get_element(make_interest('/a'))
	assert cr0 == co0

