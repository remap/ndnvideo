#! /usr/bin/env python

from pyccn import *
import utils

handle = CCN.CCN()
key = handle.getDefaultKey()

fc = utils.FlowController('/content', handle)

fc.put(utils.packet('/content/1', "hello 1", key))
fc.put(utils.packet('/content/2', "hello 2", key))
fc.put(utils.packet('/content/3', "hello 3", key))

handle.run(-1)

