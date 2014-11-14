import os
import requests
from collections import defaultdict

def id_to_backend(appId):
	return appId.replace('/', '_')

def id_to_url(appId):
	return ".".join(reversed(appId[1:].split('/')))

marathon_url = os.environ['MARATHON_URL']
apps = requests.get('http://%s/v2/apps' % marathon_url).json()
apps_to_load_balance = []
for app in apps['apps']:
	if 'portMappings' in app['container']['docker']:
		for portMapping in app['container']['docker']['portMappings']:
			if portMapping['containerPort'] == 80:
				apps_to_load_balance.append(app['id'])

tasks = requests.get('http://%s/v2/tasks' % marathon_url).json()
urls_per_app = defaultdict(list)
for task in tasks["tasks"]:
	if task["appId"] in apps_to_load_balance:
		url = "%s:%s" % (task["host"], task["ports"][0])
		urls_per_app[task["appId"]].append(url)


print """
global
	log 127.0.0.1   local0
	log 127.0.0.1   local1 notice
	maxconn 4096
	user haproxy
	group haproxy

defaults
        log     global
        mode    http
        option  httplog
        option  dontlognull
        option forwardfor
        option http-server-close
	timeout connect		5000
	timeout client		50000
	timeout server		50000

frontend http-in
	bind *:80
	"""

for appId in urls_per_app.keys():
	print "	acl host%s	hdr(host) -i %s" % (id_to_backend(appId), id_to_url(appId))

for appId in urls_per_app.keys():
	print "	use_backend %s if host%s" % (id_to_backend(appId), id_to_backend(appId))

for (appId, urls) in urls_per_app.iteritems():
	print """
backend %s
	balance leastconn
	option httpclose
	option forwardfor
	cookie JSESSIONID prefix
	cookie SERVERID insert indirect nocache
	""" % (id_to_backend(appId))

	for (i, url) in enumerate(urls):
		print "	server node%d %s cookie A check" % (i, url)













