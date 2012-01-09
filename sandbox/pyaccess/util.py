import time, Queue
from pyccn import CCN, Closure, ContentObject, Interest, Name

class CCNBuffer(Queue.Queue):
	def _init(self, maxsize):
		self.queue = []

	def _qsize(self):
		return len(self.queue)

	def _get(self):
		raise NotImplementedError()

	def _put(self, item):
		if not isinstance(item, ContentObject.ContentObject):
			raise ValueError("Item needs to be of ContentObject type")
#		if item in self.queue:
#			raise ValueError("Item %s is already in the buffer" % item)
#		item_name = Name.Name(item.name)
#		name = str(item_name)
		self.queue.append(item)

	def _get_element(self, interest):
		self.queue.sort()
		for co in enumerate(self.queue):
			if co[1].matchesInterest(interest):
				print "returning %s" % co[0]
				return self.queue.pop(co[0])
		raise ValueError("whaaa?")

	def get_element(self, interest, block=True, timeout=None):
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
					raise Empty
			elif timeout is None:
				while not self._qsize():
					self.not_empty.wait()
			elif timeout < 0:
				raise ValueError("'timeout' must be a positive number")
			else:
				endtime = _time() + timeout
				while not self._qsize():
					remaining = endtime - _time()
					if remaining <= 0.0:
						raise Empty
					self.not_empty.wait(remaining)
			item = self._get_element(interest)
			self.not_full.notify()
			return item
		finally:
			self.not_empty.release()

class FlowController(Closure.Closure):
	def __init__(self, prefix, handle):
		self.prefix = Name.Name(prefix)
		self.handle = handle
		self.content_objects = []
		self.queue = CCNBuffer(50)

		self.cleanup_time = 15 * 60 # keep responses for 15 min
		handle.setInterestFilter(self.prefix, self)

	def put(self, co):
#		self.content_objects.append((time.time(), co))
#		print "storing: %s" % co.name
		self.queue.put(co)

	def dispatch(self, interest, elem):
		if time.time() - elem[0] > self.cleanup_time:
			return False
		elif elem[1].matchesInterest(interest):
			self.handle.put(elem[1])
			return False
		return True

	def upcall(self, kind, info):
		if kind in [Closure.UPCALL_FINAL, Closure.UPCALL_CONSUMED_INTEREST]:
			return Closure.RESULT_OK

		if kind != Closure.UPCALL_INTEREST:
			print("Got weird upcall kind: %d" % kind)
			return Closure.RESULT_ERR

		co = self.queue.get_element(info.Interest)
		print "serving %s" % co.name
		self.handle.put(co)
		return Closure.RESULT_INTEREST_CONSUMED

#		f = lambda elem: self.dispatch(info.Interest, elem)
#
#		new = []
#		consumed = False
#		for elem in self.content_objects:
#			if consumed or f(elem):
#				new.append(elem)
#				continue
#			print("Consuming %s" % elem[1].name)
#			consumed = True
#		self.content_objects = new

#		return Closure.RESULT_INTEREST_CONSUMED if consumed else Closure.RESULT_OK

class VersionedPull(Closure.Closure):
	def __init__(self, base_name, callback, handle=CCN.CCN(), version=None, latest=True):
		# some constants
		self.version_marker = '\xfd'
		self.first_version_marker = self.version_marker
		self.last_version_marker = '\xfe\x00\x00\x00\x00\x00\x00'

		self.base_name = Name.Name(base_name)
		self.callback = callback
		self.handle = handle
		self.latest_version = version if version else self.first_version_marker
		self.start_with_latest = latest

	def build_interest(self, latest):
		if self.start_with_latest:
			latest=True
			self.start_with_latest = False

		excl = Interest.ExclusionFilter()
		excl.add_any()
		excl.add_name(Name.Name([self.latest_version]))
		# expected result should be between those two names
		excl.add_name(Name.Name([self.last_version_marker]))
		excl.add_any()

		interest = Interest.Interest(name=self.base_name, exclude=excl, \
			minSuffixComponents=3, maxSuffixComponents=3)
		interest.childSelector = 1 if latest else 0
		return interest

	def fetchNext(self, latest=False):
		interest = self.build_interest(latest)
		co = self.handle.get(interest.name, interest)

		if co:
			base_len = len(self.base_name)
			self.latest_version = co.name[base_len]

		return co

	def requestNext(self, latest=False):
		interest = self.build_interest(latest)
		self.handle.expressInterest(interest.name, self, interest)

	def upcall(self, kind, info):
		if kind == Closure.UPCALL_FINAL:
			return Closure.RESULT_OK

		# update version
		if kind in [Closure.UPCALL_CONTENT, Closure.UPCALL_CONTENT_UNVERIFIED]:
			base_len = len(self.base_name)
			self.latest_version = info.ContentObject.name[base_len]

		self.callback(kind, info)

		return Closure.RESULT_OK

if __name__ == '__main__':
	pass
