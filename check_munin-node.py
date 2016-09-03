#! /usr/bin/env python
#coding: utf-8
#åäö

import socket
import select
import optparse
import sys
import os
import time
import traceback

EXIT_UNKNOWN, EXIT_CRITICAL, EXIT_WARNING, EXIT_OK = 3, 2, 1, 0

class MuninNode(object):
	def __init__(self, host, port, ipv6=False):
		if ipv6:
			socket_family = socket.AF_INET6
		else:
			socket_family = socket.AF_INET
		self._s = socket.socket(socket_family)
		self._hostport = socket.getaddrinfo(host, port, socket_family, socket.SOCK_STREAM)[0][4]
		self.data = dict()

	def enable_tls(ca, cert, key):
		import ssl
		context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
		context.options |= ssl.OP_NO_SSLv2
		context.options |= ssl.OP_NO_SSLv3
		context.verify_mode = ssl.CERT_REQUIRED
		context.check_hostname = True

		self._s = context.wrap_socket(self._s,
		                              server_hostname = self._hostport[0],
					      ca_certs = ca,
					      certfile = cert,
					      keyfile = key)

	def getdata(self, command):
		s.connect(self._hostport)
		s.send("%s\nquit\n"%command)
		filtered_rows = list()
		buf = s.recv(1024)
		broken_line = ""
		while True:
			# split the received data and previously broken lines by newline
			s_buf = (broken_line + buf).split("\n")
			# did we get a broken line?
			if s_buf[-1]:
				broken_line = s_buf[-1]
				del s_buf[-1]
			else:
				broken_line = ""
			# clean up comments from data received from munin-node
			for row in s_buf:
				clean_row = row.strip(" .")
				if not (not clean_row or clean_row[0] == "#"):
					filtered_rows.append(clean_row)
			# read more data
			buf = s.recv(1024)
			if buf:
				continue
			time.sleep(0.1)
			buf = s.recv(1024)
			if not buf:
				break
		s.close()
		return filtered_rows

	def listmodules(self):
		return self.getdata("list")[0].split(" ")

	def parsedata(self, data, parsed):
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

	def fetchall(self, module):
		data = self.getdata("config %s\nfetch %s"%(module,module))
		self.parsedata(data, self.data)

	def override_levels(self, overrides):
		for override in overrides:
			try:
				name, value = override.split(".", 1)
				key, level = value.split("=", 1)
			except Exception as e:
				raise Exception("Syntax error in overrides")
			if not self.data.has_key(name):
				raise Exception("Override not possible, nonexistent path")
			self.data[name][key]=level

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
	value = float(data["value"])
	minl, maxl = parse_level(data[level].strip(" "))
	if minl and value < minl:
		return -1
	elif maxl and value > maxl:
		return 1
	else:
		return 0

if __name__ == "__main__":
	parser = optparse.OptionParser("usage: %prog [options] [level overrides]")
	parser.add_option("-H", "--host", dest="host", default="localhost")
	parser.add_option("-p", "--port", dest="port", default=4949, type="int")
	parser.add_option("-M", "--module", dest="module")
	parser.add_option("-L", "--list", dest="listmodules", default=False, action="store_true")
	parser.add_option("-d", "--debug", dest="debug", default=False, action="store_true")
	parser.add_option("-6", "--ipv6", dest="ipv6", default=False, action="store_true")
	parser.add_option("-t", "--tls", dest="tls", default=False, action="store_true")
	parser.add_option("--cacert", dest="cacert")
	parser.add_option("--cert", dest="cert")
	parser.add_option("--key", dest="key")
	opts, rest = parser.parse_args(sys.argv[1:])

	mn = MuninNode(opts.host, opts.port, opts.ipv6)

	if opts.listmodules:
		print "\n".join(mn.listmodules())
		sys.exit(EXIT_UNKNOWN)

	if not opts.module:
		sys.stderr.write("ERROR: No module selected\n");
		sys.stderr.flush()
		sys.exit(EXIT_UNKNOWN)

	if opts.tls:
		key = opts.key or opts.cert
		mn.enable_tls(opts.cacert, opts.cert, key)

	try:
		mn.fetchall(opts.module)
		mn.override_levels(rest)
		ret = EXIT_OK
		output = {"critical": list(), "warning": list(), "ok": list()}
		p_exception = set()
		for basename, config in mn.data.iteritems():
			if basename == "graph":
				continue
			try:
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
					p_exception.add(("Should have threshold(s) when getting here", str(basename), str(config)))
			except KeyError as ke:
				# no value in result from munin-node
				if ke.message == "value":
					continue
		if not (output["critical"] or output["warning"] or output["ok"]):
			if p_exception:
				raise Exception("Should have threshold(s) when getting here", *p_exception)
			else:
				raise Exception("No such module")
		for level in ("critical","warning","ok"):
			for row in output[level]:
				print row
		sys.exit(ret)
	except Exception as e:
		print "UNKNOWN, %s"%(e)
		if opts.debug:
			traceback.print_exc()
		sys.exit(EXIT_UNKNOWN)
