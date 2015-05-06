REGISTRY_OPTS=--name registry \
	-p 5000:5000 \
	-e MIRROR_SOURCE=https://registry-1.docker.io \
	-e MIRROR_SOURCE_INDEX=https://index.docker.io \
	-e MIRROR_TAGS_CACHE_TTL=172800 \
	-e GUNICORN_OPTS=[--preload] \
	-v ${CURDIR}/registry:/tmp/registry/

MESOS_MASTER_OPTS=--name mesos-master \
	--link zookeeper:zookeeper \
	-p 5050:5050 \
	-e MESOS_QUORUM=1 \
	-e MESOS_ZK=zk://zookeeper:2181/mesos \
	-e MESOS_WORK_DIR=/var/lib/mesos

MESOS_SLAVE_OPTS=--name mesos-slave \
	--privileged \
	--restart=always \
	--link zookeeper:zookeeper \
	--link registry:registry \
	-h mesos-slave \
	-e MESOS_MASTER=zk://zookeeper:2181/mesos \
	-e MESOS_CONTAINERIZERS="docker,mesos" \
	-e MESOS_EXECUTOR_REGISTRATION_TIMEOUT="5mins" \
	-e DOCKER_DAEMON_ARGS="--insecure-registry=registry:5000"

MARATHON_OPTS=--name marathon \
	--link zookeeper:zookeeper \
	-p 8080:8080

MARATHON_CMD=/opt/marathon/bin/start --master zk://zookeeper:2181/mesos --zk_hosts zookeeper:2181 --task_launch_timeout 300000

HAPROXY_OPTS=--name haproxy \
	--link marathon:marathon \
	--link mesos-slave:mesos-slave \
	-p 80:80 \
	-e MARATHON_URL=marathon:8080 \
	-e MARATHON_LOGIN="login" \
	-e MARATHON_PASSWORD="password"

build:
	docker build -t choko/mesos mesos/
	docker build -t choko/mesos-master mesos-master/
	docker build -t choko/mesos-slave mesos-slave/
	docker build -t choko/marathon marathon/
	docker build -t choko/zookeeper zookeeper/
	docker build -t choko/haproxy haproxy/

pull:
	docker pull registry:0.9.0
	docker pull choko/zookeeper
	docker pull choko/marathon
	docker pull choko/mesos-master
	docker pull choko/mesos-slave
	docker pull choko/haproxy

run:
	docker run ${REGISTRY_OPTS} -d registry
	docker run --name zookeeper -d choko/zookeeper
	docker run ${MESOS_MASTER_OPTS} -d choko/mesos-master
	docker run ${MARATHON_OPTS} -d choko/marathon ${MARATHON_CMD}
	docker run ${MESOS_SLAVE_OPTS} -d choko/mesos-slave

run_haproxy:
	docker run ${HAPROXY_OPTS} -i -t --rm choko/haproxy

stop:
	docker rm `docker kill -s 9 registry zookeeper mesos-master mesos-slave marathon`
