# gunicorn configuration for the API host.
#
# Gunicorn loads this file automatically when its working directory is the one
# holding it, so no -c flag appears in the systemd unit and none is needed: the
# unit sets WorkingDirectory to this directory. That auto-discovery is easy to
# miss when reading the unit alone — nothing there mentions this file.
#
# Command-line flags in the unit's ExecStart still win over anything set here.
#
# This file deliberately holds ONLY settings that are the same on every host.
# Per-host wiring — the bind address and the worker count — stays in the systemd
# unit, because a unix-socket host and a TCP host genuinely disagree about it and
# a value here would be silently overridden on whichever host passes the flag.

# Longer than the idle timeout of the load balancer in front of this host (60s on
# the ALB), so gunicorn is never the side that closes a pooled connection first.
#
# When the application's keepalive is the SHORTER of the two, the balancer keeps
# reusing a connection gunicorn has already decided to close: the request lands in
# a socket being torn down and the client gets a 502. It is intermittent and
# load-dependent, so it is painful to attribute to the right layer.
#
# Gunicorn's default is 2 seconds, well under any balancer's idle timeout. Raise
# this if the ALB's idle_timeout.timeout_seconds is ever raised above 75.
#
# NOTE the spelling. The config-file setting is `keepalive`, one word, while the
# command-line flag is `--keep-alive`, hyphenated — so translating the flag into
# this file invites writing `keep_alive`. Gunicorn skips names it does not
# recognize ("Ignore unknown names" in its config loader), so that misspelling
# produces no error, no warning, and no effect: the value silently stays 2.
keepalive = 75
