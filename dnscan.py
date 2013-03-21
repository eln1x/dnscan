#!/usr/bin/env python
#
# dnscan copyright (C) 2013 rbsec
# Licensed under GPLv3, see LICENSE for details
#

import getopt
import Queue
import sys
import threading

try:
    import dns.query
    import dns.resolver
    import dns.zone
except:
    out.fatal("Module dnspython missing (python-dnspython)")

# Usage: dnscan.py <domain name> <wordlist>

class scanner(threading.Thread):
    def __init__(self, queue):
        global wildcard
        threading.Thread.__init__(self)
        self.queue = queue

    def get_name(self, domain):
            global wildcard
            try:
                if sys.stdout.isatty():
                    sys.stdout.write(domain + "                              \r")
                    sys.stdout.flush()
                res = lookup(domain)
                for rdata in res:
                    if wildcard:
                        if rdata.address == wildcard:
                            return
                    print rdata.address + " - " + domain
                if domain != target:    # Don't scan root domain twice
                    add_target(domain)  # Recursively scan subdomains
            except:
                pass

    def run(self):
        while True:
            try:
                domain = self.queue.get(timeout=1)
            except:
                return
            self.get_name(domain)
            self.queue.task_done()


class output:
    def status(self, message):
        print col.blue + "[*] " + col.end + message

    def good(self, message):
        print col.green + "[+] " + col.end + message

    def warn(self, message):
        print col.red + "[-] " + col.end + message

    def fatal(self, message):
        print col.red + "FATAL: " + col.end + message


class col:
    if sys.stdout.isatty():
        green = '\033[32m'
        blue = '\033[94m'
        red = '\033[31m'
        end = '\033[0m'
    else:
        green = ""
        blue = ""
        red = ""
        end = ""

def lookup(domain):
    try:
        res = resolver.query(domain, 'A')
        return res
    except:
        return

def get_wildcard(target):
    res = lookup("nonexistantdomain" + "." + target)
    if res:
        out.good("Wildcard domain found - " + res[0].address)
        return res[0].address
    else:
        out.good("No wildcard domain found")

def get_nameservers(target):
    try:
        ns = resolver.query(target, 'NS')
        return ns
    except:
        return

def zone_transfer(domain, ns):
    out.good("Trying zone transfer against " + str(ns))
    try:
        zone = dns.zone.from_xfr(dns.query.xfr(str(ns), domain, relativize=False),
                                 relativize=False)
        out.good("Zone transfer sucessful")
        names = zone.nodes.keys()
        names.sort()
        for n in names:
            print zone[n].to_text(n)    # Print raw zone
        sys.exit()
    except Exception, e:
        pass

def add_target(domain):
    for word in wordlist:
        queue.put(word + "." + domain)

def get_args():
    global target,wordlist,num_threads
    target = None
    wordlist = None
    num_threads = 8
    if sys.argv[1:]:
        optlist, args = getopt.getopt(sys.argv[1:], 'hd:w:t:', ["domain=", "wordlist=", "threads="])
        for o, a in optlist:
            if o == "-h":
                usage()
            elif o in ("-d", "--domain"):
                target = a
            elif o in ("-w", "--wordlist"):
                try:
                    wordlist = open(a).read().splitlines()
                except:
                    out.fatal("Could not open wordlist " + a)
                    sys.exit(1)
            elif o in ("-t", "--threads"):
                try:
                    num_threads = int(a)
                    if num_threads < 1:
                        num_threads = 1
                    elif num_threads > 32:
                        num_threads = 32
                    print num_threads
                except:
                    out.fatal("Thread count must be between 1 and 32")
                    sys.exit(1)

    if target is None or wordlist is None:
        usage()

def usage():
    print "Usage: dnscan.py -d <domain> -w <wordlist> [OPTIONS]\n"
    print "Mandatory Arguments:"
    print "\t-d, --domain\t\tTarget domain"
    print "\t-w, --wordlist\t\tWordlist"
    print "\nOptional Arguments:"
    print "\t-t, --threads\t\tNumber of threads to use (1-32)"
    sys.exit(1)

if __name__ == "__main__":
    global wildcard, queue, num_threads, resolver
    out = output()
    get_args()
    queue = Queue.Queue()
    resolver = dns.resolver.Resolver()
    resolver.timeout = 1

    nameservers = get_nameservers(target)
    targetns = []       # NS servers for target
    for ns in nameservers:
        ns = str(ns)[:-1]   # Removed trailing dot
        res = lookup(ns)
        for rdata in res:
            targetns.append(rdata.address)
        zone_transfer(target, ns)
#    resolver.nameservers = targetns     # Use target's NS servers for lokups
# Missing results using domain's NS - removed for now

    out.warn("Zone transfer failed")
    wildcard = get_wildcard(target)
    out.status("Scanning " + target)
    queue.put(target)   # Add actual domain as well as subdomains
    add_target(target)

    for i in range(num_threads):
        t = scanner(queue)
        t.setDaemon(True)
        t.start()

    try:
        for i in range(num_threads):
            t.join(1024)       # Timeout needed or threads ignore exceptions
    except KeyboardInterrupt:
        out.fatal("Quitting...")
