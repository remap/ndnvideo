#
# Copyright (c) 2011, Regents of the University of California
# BSD license, See the COPYING file for more information
# Written by: Derek Kulinski <takeda@takeda.tk>
#

from pyccn import Interest, Name, CCN, Closure
import time, Queue

class FlowController(Closure.Closure):
	def __init__(self, prefix, handle):
		self.prefix = Name.Name(prefix)
		self.handle = handle
		self.content_objects = []
		self.queue = Queue.Queue(500)

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

		co = self.queue.get()
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

import struct, vlc_access
from pyccn import *

h = CCN.CCN()
key = h.getDefaultKey()
keylocator = Key.KeyLocator(key)

si = ContentObject.SignedInfo()
si.type = ContentObject.ContentType.CCN_CONTENT_DATA
si.publisherPublicKeyDigest = key.publicKeyID
si.keyLocator = keylocator

basename = Name.Name('/testmovie')
fc = FlowController(basename, h)

def segment(segment):
	return b'\x00' + struct.pack('!Q', segment).lstrip('\x00')

def getSegment(seg):
	global h, base

	name = Name.Name(base)
	name += segment(seg)

	co = h.get(name)
	return co.content

def preparePacket(seg, data):
	global basename, si, key

	co_name = Name.Name(basename)
	co_name += segment(seg)
#	print("preparing %s" % co_name)

	co = ContentObject.ContentObject()
	co.content = data
	co.name = co_name
	co.signedInfo = si
	co.sign(key)

	return co

counter = 0
buf = b''
def write(data):
	global counter, fc, buf

#	if len(fc.content_objects) > 2000:
#		return None
#	else:
#		print("length: %d" % len(fc.content_objects))

	length = 0
	for i in data:
		buf += i[0]
		length += len(i[0])
#		print "%x %d %d %d" % (i[1], i[2], i[3], i[4])

	s = len(buf)
	if s > 4722:
		packet = preparePacket(counter, buf)
		counter += 1
		buf = b''
		fc.put(packet)

	return long(length)

vlc_access.set_callback("write", write)

def listen():
	global h

	h.run(-1)

import threading
thread = threading.Thread(target=listen)
thread.start()

