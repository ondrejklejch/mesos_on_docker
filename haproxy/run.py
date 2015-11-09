import os
import time
import requests
import subprocess
from collections import defaultdict

def id_to_backend(appId):
	return appId.replace('/', '_')

def id_to_url(appId):
	return ".".join(reversed(appId[1:].split('/')))

def create_config(marathon_url, login, password):
	apps = requests.get('http://%s/v2/apps' % marathon_url, auth=(login, password)).json()
	apps_to_load_balance = []
	for app in apps['apps']:
		if 'portMappings' in app['container']['docker'] and app['container']['docker']['portMappings'] != None:
			for portMapping in app['container']['docker']['portMappings']:
				if portMapping['containerPort'] == 80:
					apps_to_load_balance.append(app['id'])

	tasks = requests.get('http://%s/v2/tasks' % marathon_url, headers={'Accept': 'application/json'}, auth=(login, password)).json()
	urls_per_app = defaultdict(list)
	for task in tasks["tasks"]:
		if task["appId"] in apps_to_load_balance:
			url = "%s:%s" % (task["host"], task["ports"][0])
			urls_per_app[task["appId"]].append(url)

	config = """
global
	log 127.0.0.1   local0
	log 127.0.0.1   local1 notice
	maxconn 4096
	user haproxy
	group haproxy
	tune.ssl.default-dh-param 4096

defaults
	log     global
	mode    http
	option  httplog
	option  dontlognull
	option forwardfor
	option http-server-close
	timeout connect		10000
	timeout client		60000
	timeout server		60000

frontend https-in
	bind *:443 ssl crt /etc/haproxy/www.cloudasr.com.pem crt /etc/haproxy/api.cloudasr.com.pem
	reqadd X-Forwarded-Proto:\ https

	use_backend _cloudasr.com_www if { hdr(host) -i www.cloudasr.com }
	use_backend _cloudasr.com_api if { hdr(host) -i api.cloudasr.com }

frontend http-in
	bind *:80

	acl demo hdr(host) -i demo.cloudasr.com
	redirect location http://www.cloudasr.com/demo code 301 if demo
	acl no_www hdr(host) -i cloudasr.com
	redirect prefix http://www.cloudasr.com code 301 if no_www
	redirect scheme https code 301 if { hdr(host) -i www.cloudasr.com } !{ ssl_fc }
	redirect scheme https code 301 if { hdr(host) -i api.cloudasr.com } !{ ssl_fc }
"""

	for appId in urls_per_app.keys():
		config += "	acl host%s	hdr(host) -i %s\n" % (id_to_backend(appId), id_to_url(appId))

	for appId in urls_per_app.keys():
		config += "	use_backend %s if host%s\n" % (id_to_backend(appId), id_to_backend(appId))

	for (appId, urls) in urls_per_app.iteritems():
		config += """
backend %s
	balance leastconn
	option httpclose
	option forwardfor
	cookie JSESSIONID prefix
	cookie SERVERID insert indirect nocache
""" % (id_to_backend(appId))

		for (i, url) in enumerate(urls):
			config += "	server node%d %s cookie A check\n" % (i, url)

	return config

if __name__ == '__main__':
	marathon_url = os.environ.get('MARATHON_URL')
	login = os.environ.get('MARATHON_LOGIN', None)
	password = os.environ.get('MARATHON_PASSWORD', None)

	last_config = None
	while True:
		config = create_config(marathon_url, login, password)

		if last_config != config:
			with open('/etc/haproxy/haproxy.cfg', 'w') as f:
				f.write(config)

			print "%s Configuration changed" % time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
			subprocess.call(("service", "haproxy", "reload"))
			last_config = config

		time.sleep(10)

