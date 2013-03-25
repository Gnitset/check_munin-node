#! /usr/bin/env python
#coding: utf-8
#åäö

import socket
import select
import optparse
import sys
import os

class MuninNode(Object):
	def __init__(self, hostport):
		self._hostport=hostport
		self._s=socket.socket()
		self._s.setblocking(False)

	def connect(self):
		raise NotImplemented

	def getdata(self, command):
		self.connect()
		self._s.send("%s\n"%command)
		data=[]
		done=False:
		while not done:
			(r,w,e)=select.select([self._s],[],[self._s],60)
			if self._s in e:
				print "socket in error :("
			if self._s in r:
				data.append(self._s.recv(1024))
				if data[-1].endswith("\n.\n"):
					done=True
		return ''.join(data)

	def parsedata(self, data):
		parsed=dict()
		for line in data.split("\n"):
			if line.startswith("# "):
				continue
			mnkey,value=line.strip().split(".",1)
			mntype,mnvalue=value.strip().split(" ",1)
			if not parsed.has_key(mnkey):
				parsed[mnkey]=dict()
			parsed[mnkey][mntype]=mnvalue
		return parsed

	def config(self, module):
		raise NotImplemented

	def fetch(self, module):
		raise NotImplemented

if __name__ == "__main__":
	parser=optparse.OptionParser("usage: %prog [options]")
	parser.add_option("-H", "--host", dest="host", default="localhost")
	parser.add_option("-p", "--port", dest="port", default=4949, type="int")
	parser.add_option("-M", "--module", dest="module")
	parser.add_option("-S", "--sub-module", dest="sub_module", default=None)
	opts, rest=parser.parse_args(sys.argv[1:])

	if not opts.module:
		sys.stderr.write("ERROR: No module selected\n");
		sys.stderr.flush()
		sys.exit(3)

	mn=MuninNode((opts.host,opts.port))

	mn.config(opts.module)
	mn.fetch(opts.module)
