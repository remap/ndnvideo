#! /usr/bin/env python

class Window():
	def __init__(self, window, request_cb, receive_cb):
		self.window = window
		self.request_cb = request_cb
		self.receive_cb = receive_cb

	def reset(self, position = 0):
		self._buf = {}
		self._position = position
		self._requested = position - 1
		self.request_data()

	def put(self, number, data):
		self._buf[str(number)] = data
		self.push_out()

	def request_data(self):
		stop = self._position + self.window - 1
		while self._requested < stop:
			self._requested += 1
			if not self.request_cb(self._requested):
				return

	def push_out(self):
		while self._buf.has_key(str(self._position)):
			data = self._buf[str(self._position)]
			self.receive_cb(data)

			del self._buf[str(self._position)]
			self._position += 1

		self.request_data()

if __name__ == "__main__":
	import pyccn, struct
	import sys

	handle = pyccn.CCN()
	base = pyccn.Name('/ndn/ucla.edu/apps/hydra/videostream/segments')

	def seg2num(name):
		segment = name[-1]
		num = long(struct.unpack("!Q", (8 - len(segment)) * "\x00" + segment)[0])

		return num

	class Handler(pyccn.Closure):
		def __init__(self):
			self.window = Window(20, self.gen, self.disp)

		def gen(self, pos):
			name = base.appendSegment(pos)
			handle.expressInterest(name, self)
			return True

		def disp(self, value):
			print value.name

		def upcall(self, kind, info):
			if kind == pyccn.UPCALL_FINAL:
				return pyccn.RESULT_OK

			if kind == pyccn.UPCALL_INTEREST_TIMED_OUT:
				print "Reexpressing"
				return pyccn.RESULT_REEXPRESS

			if not kind == pyccn.UPCALL_CONTENT:
				print "Got kind %d" % kind
				return pyccn.RESULT_ERR

			self.window.put(seg2num(info.ContentObject.name), info.ContentObject)


	t = Handler()
	t.window.reset(0)
	handle.run(-1)
