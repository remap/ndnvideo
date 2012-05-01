#! /usr/bin/env python

import sys, pyccn

def get_latest_version(name):
	n = pyccn.Name(name)
	i = pyccn.Interest(childSelector = 1, answerOriginKind = pyccn.AOK_NONE)

	handle = pyccn.CCN()
	co = handle.get(n,i)
	if co is None:
		return None

	return co.name[:len(n) + 1]

def main(args):
	if len(args) != 2:
		print "Usage: %s <name>" % args[0]
		return 1

	print get_latest_version(args[1])

if __name__ == "__main__":
	sys.exit(main(sys.argv))
