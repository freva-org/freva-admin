#!/usr/bin/env bash
# Simple script that lets us inspect stuff
#
path=$(command -v podman 2>/dev/null || true)
if [ -z "$path" ]; then
    echo "Podman is not installed on the system."
    exit 1
fi
image=$("$path" image ls --filter "reference=$1" --format "{{.Tag}}" 2>/dev/null)
if [ "$image" ];then
    tag=$(echo $image|awk '{print $0}')
    if [ "$tag" ];then
        version=$($path inspect $1:$tag --format='{{index .Config.Labels "org.opencontainers.image.version"}}' 2> /dev/null)
        if [ "$version" ];then
            echo $version
            exit 0
        else # Fall back
            echo $tag
            exit 0
        fi
    fi
else
    echo ""
fi
