###
# DOCKER LIVE RELOADER
# Watches for tag events and reloads containers running that image, no interaction required.
###

import os
from docker import Client
from docker.utils import kwargs_from_env


# parses port list from running docker container port definition
def get_port_list(port_def):
    port_list = []

    for port in port_def:
        port_list.append(port['PrivatePort'])

    return port_list


# parses port mappings from running docker container port definition
def get_port_mapping(port_def):
    mappings = {}

    for port in port_def:
        mappings[port['PrivatePort']] = port['PublicPort']

    return mappings


# parses host entries list from running docker container inspection
def get_hosts(extra_hosts):
    hosts = {}
    for host in extra_hosts:
        host_parts = host.split(":")
        hosts[host_parts[0]] = host_parts[1]

    return hosts


# parses volume entries list from running docker container inspection
def get_volumes(container_mounts):
    volumes = []

    for mount in container_mounts:
        if mount['Source'].endswith("_data"):
            continue

        volumes.append(mount['Destination'])
    return volumes


# parses volume binds from running docker container inspection
def get_volume_binds(container_mounts):
    binds = []

    for mount in container_mounts:
        if mount['Source'].endswith("_data"):
            continue
        binds.append(mount['Source'] + ":" + mount['Destination'])

    return binds


# --- Run loop

# Connect to docker via docker.sock or TCP
if os.environ.get('DOCKER_HOST') is not None:
    kwargs = kwargs_from_env()
    kwargs['tls'].assert_hostname = False
    cli = Client(**kwargs)
else:
    cli = Client(base_url="unix://var/run/docker.sock")

# Blocking event loop
try:
    for event in cli.events(decode=True):

        # On tag events check for running containers running this image
        if event['Action'] == "tag":
            imageId = event['Actor']['ID']
            for container in cli.containers():
                name = event['Actor']['Attributes']['name'].replace(":latest", "")
                nameShort = event['Actor']['Attributes']['name']
                container_data = cli.inspect_container(container["Id"])

                # On container found remove the container and reload it preserving env, ports, and mappings
                if container_data["Config"]["Image"] == nameShort or container_data["Config"]["Image"] == name:
                    print("reloading %s\n" % event['Actor']['Attributes']['name'])

                    cli.remove_container(container["Id"], force=True)
                    result = cli.create_container(
                        image=event['Actor']['Attributes']['name'],
                        ports=get_port_list(container["Ports"]),
                        volumes=get_volumes(container_data["Mounts"]),
                        host_config=cli.create_host_config(port_bindings=get_port_mapping(container["Ports"]),
                                                           extra_hosts=get_hosts(container_data["HostConfig"]["ExtraHosts"]),
                                                           binds=get_volume_binds(container_data["Mounts"])),
                        environment=container_data["Config"]["Env"])

                    cli.start(result['Id'])

except KeyboardInterrupt:
    print("shutting down!")