#! /usr/bin/env python
#coding: utf-8
#åäö

import socket
import select
import sys
import os

if __name__ == "__main__":
	parser=optparse.OptionParser("usage: %prog [options]")
	parser.add_option("-H", "--host", dest="host")
	parser.add_option("-p", "--port", dest="port")
	parser.add_option("-M", "--module", dest="module")
	opts, rest=parser.parse_args(sys.argv[1:])

