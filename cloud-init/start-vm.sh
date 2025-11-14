#!/bin/bash
#
# Create a virtual machine for testing the freva-deployment
#
IMG="ubuntu-23.10-minimal-cloudimg-amd64.img"
PORT=8000
cd $(dirname $(readlink -f $0))
prepare () {

    mkdir -p temp
    if [ ! -f "$IMG" ];then
        wget https://cloud-images.ubuntu.com/minimal/releases/mantic/release/$IMG
        img_file=$IMG
        qemu-img resize $img_file +50G 1>&2
    else
        cp $IMG temp/ubuntu.img
        img_file=temp/ubuntu.img
    fi
    touch temp/vendor-data
    if [ ! -f ~/.ssh/id_rsa.pub ];then
        ssh-keygen -t rsa -f ~/.ssh/id_rsa.pub
    fi
    pub_key=$(cat ~/.ssh/id_rsa.pub)
    private_key=$(cat ~/.ssh/id_rsa)
    cat << EOF > temp/meta-data
instance-id: freva
local-hostname: freva

EOF
    cat << EOF > temp/user-data
#cloud-config
package_update: true
packages:
  - git
  - python3-pip
  - podman-compose
  - docker-compose
runcmd:
  - [ mkdir, -p, /opt/freva]
  - [ chown, -R, freva:admin, /opt/freva]
  - [ chmod, -R, 775, /opt/freva]
  - [ loginctl, enable-linger, freva]
groups:
  admingroup: [root, sys]
users:
  - name: freva
    lock_passwd: true
    gecos: Freva Test
    groups: users, admin
    plain_text_passwd: "freva"
    sudo: "ALL=(ALL) NOPASSWD:ALL"
    shell: /bin/bash
    ssh_authorized_keys:
      - $pub_key
  - name: freva-admin
    lock_passwd: true
    gecos: Freva Admin User
    groups: users, admin
    shell: /bin/bash
ssh_deletekeys: false
ssh_keys:
    rsa_public: $pub_key
    rsa_private: |
$(cat ~/.ssh/id_rsa| sed 's/^/      /g')
EOF
echo $img_file
}

kill_vm () {
    if [ -f temp/vm.log ];then
        echo "#### RECEIVED KILL SIGNAL! ####" >> temp/vm.log
        pid=$(ps aux|grep 'tail -f temp/vm.log' |grep -v grep |grep $(whoami)|awk '{print $2}')
        if [ "$pid" ];then
            sleep 0.5
            kill $pid
        fi
    fi
    for file in httpd vm;do
        if [ -f temp/$file.pid ];then
            kill -9 $(cat temp/$file.pid) 2> /dev/null
        fi
    done
    rm -rf temp 2> /dev/null
    }

start () {
    kill_vm
    local img_file=$(prepare)
    echo -e Starting http server for config injection...
    python3 -m http.server $PORT --directory temp &
    echo $! > temp/httpd.pid
    sleep 2
    if [ -z "$(ps aux|grep -v grep|awk '{print $2}'|grep $(cat temp/httpd.pid))" ];then
        kill_vm
        exit 1
    fi
    qemu-system-x86_64                                              \
        -name freva-deployment                                      \
        -net nic                                                    \
        -net user,hostfwd=tcp::2222-:22,hostfwd=tcp::5555-:80       \
        -machine accel=kvm:tcg                                      \
        -cpu host                                                   \
        -m 4G                                                       \
        -nographic                                                  \
        -hda $img_file                                              \
        -async-teardown                                             \
        -smbios type=1,serial=ds="nocloud;s=http://10.0.2.2:$PORT" &> temp/vm.log &
    echo $! > temp/vm.pid
    tail -f temp/vm.log |grep -v 'freva login:'
    kill_vm
}

# Function to display usage information
usage () {
    echo "Usage: $(basename $0) [-k|--kill], [-p|--port PORT]"
    echo "Create a new virtual machine (VM) ready for freva deployment."
    echo "Options:"
    echo "  -k, --kill     Kill the virtual machine"
    echo "  -p, --port     Set the port of the service that is used to configure the VM default: $PORT"
    exit 1
}

# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
    case "$1" in
        -k|--kill)
            kill_vm
            exit 0
            ;;
        -p|--port)
            if [[ -n "$2" && ! "$2" =~ ^-[^-] ]]; then
                PORT="$2"
                shift
            else
                usage
            fi
            ;;
        --port=*)
            PORT="${1#*=}"
            ;;
        *)
            usage
            ;;
    esac
    shift
done

# If no arguments were provided, start the VM
start
