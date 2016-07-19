import os
import subprocess
import sys
import time

import splunk.clilib.cli_common

import requests

print "Initializing " + os.environ['HOSTNAME'] + " as SHC Member"

def wait_for_cluster_master():
    """
    At first let's wait for the Cluster Master (wait maximum for 5 minutes)
    """
    for x in xrange(1, 300):
        try:
            # This url does not require authentication, ignore certificate
            response = requests.get("https://cluster-master:8089/services/server/info?output_mode=json", verify=False)
            if response.status_code == 200:
                server_roles = response.json()["entry"][0]["content"]["server_roles"]
                if "cluster_master" in server_roles:
                    return
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)


wait_for_cluster_master()

splunk_bin = os.path.join(os.environ['SPLUNK_HOME'], "bin", "splunk")

sys.stdout.flush()
sys.stderr.flush()

# Initialize Splunk as Search Head
subprocess.check_call(
    [
        splunk_bin,
        "edit",
        "cluster-config",
        "-auth", "admin:changeme",
        "-mode", "searchhead",
        "-master_uri", "https://cluster-master:8089",
        "-secret", "example_cluster_secret"
    ]
)

sys.stdout.flush()
sys.stderr.flush()

# Initialize Splunk as SHC Member
subprocess.check_call(
    [
        splunk_bin,
        "init",
        "shcluster-config",
        "-auth", "admin:changeme",
        "-secret", "example_shc_secret",
        "-replication_port", "9889",
        "-mgmt_uri", "https://%s:8089" % os.environ['HOSTNAME'],
        "-replication_factor", os.environ.get("INIT_SHC_REPLICATION_FACTOR", 3),
        "-conf_deploy_fetch_url", "https://cluster-master:8089"
    ])

sys.stdout.flush()
sys.stderr.flush()

# Set general secret on each SHC/IDXC node to use license master
server_conf_file = os.path.join(os.environ['SPLUNK_HOME'], "etc", "system", "local", "server.conf")
server_conf = splunk.clilib.cli_common.readConfFile(server_conf_file)

# Set general secret on each SHC/IDXC node to use license master
general_stanza = server_conf.setdefault("general", {})
general_stanza["pass4SymmKey"] = "example_general_secret"

splunk.clilib.cli_common.writeConfFile(server_conf_file, server_conf)

sys.stdout.flush()
sys.stderr.flush()

# Restart
subprocess.check_call(
    [
        splunk_bin,
        "restart"
    ])

sys.stdout.flush()
sys.stderr.flush()

# Initialize as local slave (should be configurable)
subprocess.check_call(
    [
        splunk_bin,
        "edit",
        "licenser-localslave",
        "-master_uri", "https://cluster-master:8089",
        "-auth", "admin:changeme"
    ])

sys.stdout.flush()
sys.stderr.flush()

subprocess.check_call(
    [
        splunk_bin,
        "restart"
    ])

sys.stdout.flush()
sys.stderr.flush()

print "Initialized " + os.environ['HOSTNAME'] + " as SHC Member"
print "If this is the first time you setup SHC you need to bootstrap a captain"
print "splunk bootstrap shcluster-captain -auth admin:changeme -servers_list \"...\""
print "or add this member to existing cluster"
print "splunk add shcluster-member -new_member_uri https://" + os.environ['HOSTNAME'] + ":8089"