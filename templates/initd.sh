#!/bin/bash
#
# keystone OpenStack Image Service
# chkconfig: - 98 02
#

# Source function library.
. /etc/init.d/functions

prog="{{ prog }}"
option="{{ option }}"
user="{{ user }}"
exec="{{ prefix }}/bin/$prog"
pidfile="/var/run/$prog.pid"


start_exec() {
    $exec $option &> /dev/null &
    pid=$!

    if [ -d /proc/$pid ]; then
        echo $pid > $pidfile
        exit 0
    fi

    exit 1
}

start() {
    [ -x $exec ] || exit 5

    echo -n "Starting $prog: "
    daemon --user $user "`start_exec`"

    echo
    [ -d /proc/`cat $pidfile` ] || return 1

    return 0
}

stop() {
    echo -n "Shutting down $prog: "
    killproc -p $pidfile $prog
    retval=$?

    echo
    return $retval
}

rh_status() {
    status -p $pidfile $prog
}

rh_status_q() {
    rh_status 2>&1
}

case "$1" in
    start)
        rh_status_q && exit 0
        start
    ;;
    stop)
        rh_status_q || exit 0
        stop
    ;;
    status)
        rh_status
    ;;
    restart)
        stop
        start
    ;;
    *)
        echo "Usage: $prog> {start|stop|status|restart"
        exit 1
    ;;
esac
exit $?
