#! /usr/bin/env python
#coding: utf-8
#åäö

import socket
import select
import optparse
import sys
import os

class MuninNode(object):
	def __init__(self, hostport):
		self._hostport=hostport
		self.data=dict()

	def connect(self):
		self._s=socket.socket()
		self._s.connect(self._hostport)
		self._s.setblocking(False)

	def disconnect(self):
		self._s.send("quit\n")
		self._s.shutdown(socket.SHUT_RDWR)
		self._s.close()

	def getdata(self, command, end_str="\n.\n"):
		self.connect()
		send_pipe=list(["%s"%command])
		extra_data=""
		done=False
		rows=[]
		while not done:
			if send_pipe:
				write_socks=[self._s]
			else:
				write_socks=[]
			(r,w,e)=select.select([self._s],write_socks,[self._s],3)
			if self._s in e:
				print "socket in error :("
			if not r and not w and not e:
				print "timeout"
				break
			if self._s in w:
				wlen=self._s.send(send_pipe[0])
				if wlen == len(send_pipe[0]):
					del send_pipe[0]
				else:
					send_pipe[0]=send_pipe[0][wlen:]
			if self._s in r:
				r_data=self._s.recv(1024)
				f1_arr=[row for row in (extra_data+r_data).split("\n") if not row or row[0] != "#"]
				if len(f1_arr[-1]):
					extra_data=f1_arr[-1]
					del f1_arr[-1]
				elif "\n".join(f1_arr).endswith(end_str):
					done=True
				for row in f1_arr:
					srow=row.strip(".\n")
					if not srow:
						continue
					rows.append(srow)
		self.disconnect()
		return rows

	def listmodules(self):
		return self.getdata("list\n", "\n")[0].split(" ")

	def parsedata(self, data, parsed=dict()):
		for line in data:
			try:
				mnkey,value=line.strip().split(".",1)
			except ValueError:
				mnkey="graph"
				value=line.strip()
			try:
				mntype,mnvalue=value.strip().split(" ",1)
			except ValueError:
				print "ve,",value
				return parsed
			if not parsed.has_key(mnkey):
				parsed[mnkey]=dict()
			parsed[mnkey][mntype]=mnvalue
		return parsed

	def config(self, module):
		data=self.getdata("config %s\n"%module)
		pdata=self.parsedata(data, self.data)
		return pdata

	def fetch(self, module):
		data=self.getdata("fetch %s\n"%module)
		pdata=self.parsedata(data, self.data)
		return pdata

if __name__ == "__main__":
	parser=optparse.OptionParser("usage: %prog [options]")
	parser.add_option("-H", "--host", dest="host", default="localhost")
	parser.add_option("-p", "--port", dest="port", default=4949, type="int")
	parser.add_option("-M", "--module", dest="module")
	parser.add_option("-S", "--sub-module", dest="sub_module", default=None)
	parser.add_option("-L", "--list", dest="listmodules", default=False, action="store_true")
	opts, rest=parser.parse_args(sys.argv[1:])

	mn=MuninNode((opts.host,opts.port))

	if opts.listmodules:
		print "\n".join(mn.listmodules())
		sys.exit(4)

	if not opts.module:
		sys.stderr.write("ERROR: No module selected\n");
		sys.stderr.flush()
		sys.exit(3)

	mn.config(opts.module)
	mn.fetch(opts.module)
	ret=0
	for k,v in mn.data.iteritems():
		if k == "graph" or not (v.has_key("warning") or v.has_key("critical")):
			continue
		if v.has_key("critical"):
			if ":" in v["critical"]:
				print "nooooo"
			elif float(v["value"]) >= float(v["critical"]):
				print "Critical, %(label)s, %(value)s over threshold %(critical)s"%v
				ret=2
				continue
		if v.has_key("warning"):
			if ":" in v["warning"]:
				print "nooooo"
			elif float(v["value"]) >= float(v["warning"]):
				print "Warning, %(label)s, %(value)s over threshold %(warning)s"%v
				ret=2
				continue
