#! /usr/bin/env python
#coding: utf-8
#åäö

import socket
import select
import optparse
import sys
import os

EXIT_UNKNOWN, EXIT_CRITICAL, EXIT_WARNING, EXIT_OK = 3, 2, 1, 0

class MuninNode(object):
	def __init__(self, hostport):
		self._hostport = hostport
		self.data = dict()

	def connect(self):
		self._s = socket.socket()
		self._s.connect(self._hostport)
		self._s.setblocking(False)

	def disconnect(self):
		self._s.send("quit\n")
		self._s.shutdown(socket.SHUT_RDWR)
		self._s.close()

	def getdata(self, command, end_str = "\n.\n"):
		self.connect()
		send_pipe = list(["%s"%command])
		extra_data = ""
		done = False
		rows = []
		while not done:
			if send_pipe:
				write_socks = [self._s]
			else:
				write_socks = []
			(r, w, e)=select.select([self._s], write_socks, [self._s], 3)
			if self._s in e:
				print "socket in error :("
				sys.exit(EXIT_UNKNOWN)
			if not r and not w and not e:
				# we probably failed to detect that we got all data
				break
			if self._s in w:
				wlen = self._s.send(send_pipe[0])
				# did we succeed in sending all data
				if wlen == len(send_pipe[0]):
					del send_pipe[0]
				# save the data not sent to try again when possible
				else:
					send_pipe[0] = send_pipe[0][wlen:]
			if self._s in r:
				r_data = self._s.recv(1024)
				f_arr = list()
				# clean up comments from data received from munin-node
				for row in (extra_data+r_data).split("\n"):
					if not row or row[0] != "#":
						f_arr.append(row)
				# did we get a broken line?
				if len(f_arr[-1]):
					extra_data = f_arr[-1]
					del f_arr[-1]
				# did we get all the data?
				elif "\n".join(f_arr).endswith(end_str):
					done = True
				# cleanup rows received
				for row in f_arr:
					srow = row.strip(".\n")
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
				mnkey, value = line.strip().split(".",1)
			except ValueError:
				# if theres no . in a line it is probably graph-info, and almost certainly unnecessary
				mnkey = "graph"
				value = line.strip()
			try:
				mntype, mnvalue = value.strip().split(" ",1)
			except ValueError:
				if mnkey == "graph":
					# like I said, ignore unnecessary data
					continue
				print "UNKNOWN, ValueError, '%s'"%value
				sys.exit(EXIT_UNKNOWN)
			if not parsed.has_key(mnkey):
				parsed[mnkey] = dict()
			parsed[mnkey][mntype] = mnvalue
		return parsed

	def config(self, module):
		data = self.getdata("config %s\n"%module)
		self.parsedata(data, self.data)

	def fetch(self, module):
		data = self.getdata("fetch %s\n"%module)
		self.parsedata(data, self.data)

def parse_level(level):
	if ":" not in level:
		return (None, float(level))
	if level[0] == ":":
		return (None, float(level[1:]))
	if level[-1] == ":":
		return (float(level[:-1]), None)
	else:
		return map(float,level.split(":"))

def check_level(data, level):
	if level not in data or not data[level]:
		return None
	value=float(data["value"])
	minl, maxl = parse_level(data[level])
	if minl and value < minl:
		return -1
	elif maxl and value > maxl:
		return 1
	else:
		return 0

if __name__ == "__main__":
	parser = optparse.OptionParser("usage: %prog [options]")
	parser.add_option("-H", "--host", dest="host", default="localhost")
	parser.add_option("-p", "--port", dest="port", default=4949, type="int")
	parser.add_option("-M", "--module", dest="module")
	parser.add_option("-S", "--sub-module", dest="sub_module", default=None)
	parser.add_option("-L", "--list", dest="listmodules", default=False, action="store_true")
	opts, rest = parser.parse_args(sys.argv[1:])

	mn = MuninNode((opts.host,opts.port))

	if opts.listmodules:
		print "\n".join(mn.listmodules())
		sys.exit(EXIT_UNKNOWN)

	if not opts.module:
		sys.stderr.write("ERROR: No module selected\n");
		sys.stderr.flush()
		sys.exit(EXIT_UNKNOWN)

	try:
		mn.config(opts.module)
		mn.fetch(opts.module)
		ret = EXIT_OK
		output = {"critical": list(), "warning": list(), "ok": list()}
		for basename, config in mn.data.iteritems():
			if basename == "graph":
				continue
			check = check_level(config, "critical")
			if check:
				output["critical"].append("Critical, %(label)s, %(value)s outside threshold c(%(critical)s)"%config)
				if ret < EXIT_CRITICAL: ret = EXIT_CRITICAL
				continue
			check = check_level(config, "warning")
			if check:
				output["warning"].append("Warning, %(label)s, %(value)s outside threshold w(%(warning)s)"%config)
				if ret < EXIT_WARNING: ret = EXIT_WARNING
				continue
			if config.has_key("critical") and config.has_key("warning"):
				output["ok"].append("OK, %(label)s, %(value)s inside thresholds c(%(critical)s), w(%(warning)s)"%config)
			elif config.has_key("critical"):
				output["ok"].append("OK, %(label)s, %(value)s inside thresholds c(%(critical)s)"%config)
			elif config.has_key("warning"):
				output["ok"].append("OK, %(label)s, %(value)s inside thresholds w(%(warning)s)"%config)
			else:
				raise Exception("Should have threshold(s) when getting here", basename, config)
		for level in ("critical","warning","ok"):
			for row in output[level]:
				print row
		sys.exit(ret)
	except Exception as e:
		print "UNKNOWN, %s %s"%(type(e), e)
		sys.exit(EXIT_UNKNOWN)
