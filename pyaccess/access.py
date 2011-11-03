from pyccn import Interest, Name, CCN, Closure
import time, threading, Queue

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

#from time import time, ctime

#print 'Today is', ctime(time())

#file = '/windows/C/Documents and Settings/takeda/Desktop/Army of Darkness (1992){BrRip.x264}[1337x][blackjesus]/Army Of Darkness {700mb}.mp4'
#block_size = 524288
#block_size = 1048576
#block_size = 128 * 4096

#fi = open(file, "r")
#fi.seek(100*1024*1024)

#def block():
#	global fi, position, block_size
#	data = fi.read(block_size)
#	return data


import struct, vlc_access
from pyccn import *

h = CCN.CCN()
#base = Name.Name('/movie/%FD%04%E0%ACL%97%60')
base = Name.Name('/testmovie')

def segment(segment):
	return b'\x00' + struct.pack('!Q', segment).lstrip('\x00')

def getSegment(seg):
	global h, base

	name = Name.Name(base)
	name += segment(seg)

	print "Requesting: %s" % name

	co = None
	tries = 3
	while not co:
		if tries <= 0:
			return ""
		co = h.get(name, None, 150)
		if co:
			return co.content
		print "retrying"
		tries -= 1

	return None

class Requests(Closure.Closure):
	def __init__(self, handle, name):
		self.queue = Queue.Queue(1000)
		self.counter = 0
		self.handle = handle
		self.name = Name.Name(name)

	def getNext(self):
		name = Name.Name(self.name)
		name += segment(self.counter)
#		print "Issuing interest %s" % name
		self.counter += 1
		self.handle.expressInterest(name, self)

	def upcall(self, kind, info):
		if kind == Closure.UPCALL_INTEREST_TIMED_OUT:
			print "timeout; reexpressiong..."
			return Closure.RESULT_REEXPRESS

		if kind == Closure.UPCALL_FINAL:
			return Closure.RESULT_OK

		if not kind in [Closure.UPCALL_CONTENT, Closure.UPCALL_CONTENT_UNVERIFIED]:
			print("Got weird upcall kind: %d" % kind)
			return Closure.RESULT_ERR

		print "putting content %s to queue" % info.ContentObject.name
		self.queue.put(info.ContentObject.content)
		self.getNext()

		return Closure.RESULT_OK

req = Requests(h, base)

counter = 0
def block():
	global req

	data = req.queue.get()
	return data

vlc_access.set_callback("block", block)

def listen():
	global h

	h.run(-1)

import threading
thread = threading.Thread(target=listen)
thread.start()

req.getNext()
