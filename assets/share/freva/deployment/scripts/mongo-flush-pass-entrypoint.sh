#!/bin/bash
set -Eeuo pipefail

MONGODB_USER=${MONGODB_USER:-"mongo"}
MONGODB_PASSWORD=${MONGODB_PASSWORD:-"{{root_passwd}}"}
LOG_FILE="/var/log/mongodb.log"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

wait_for_mongo() {
    # TODO: For a small test environment, 30 seconds was too long, but to be safe and sure in a real env, we should keep it at 30 seconds
    for i in {1..30}; do
        if mongosh --quiet --eval "db.adminCommand('ping')" &>/dev/null; then
            return 0
        fi
        sleep 1
    done
    return 1
}

reset_user() {
    log "Starting mongo without auth for user reset..."
    mongod --bind_ip_all --fork --logpath "$LOG_FILE" --noauth
    
    sleep 5
    
    log "striping existing users and creating admin user again..."
    mongosh admin --quiet --eval "
        db.dropUser('${MONGODB_USER}');
        db.createUser({
            user: '${MONGODB_USER}',
            pwd: '${MONGODB_PASSWORD}',
            roles: [
                { role: 'root', db: 'admin' },
                { role: 'userAdminAnyDatabase', db: 'admin' },
                { role: 'dbAdminAnyDatabase', db: 'admin' },
                { role: 'readWriteAnyDatabase', db: 'admin' }
            ]
        });"
    
    if [ $? -eq 0 ]; then
        log "User reset successfully"
        mongod --shutdown
        sleep 5
        return 0
    else
        log "Failed to reset user"
        mongod --shutdown
        sleep 5
        return 1
    fi
}

verify_auth() {
    log "Verifying authentication..."
    mongosh admin --quiet --eval "
        try {
            db.auth('${MONGODB_USER}', '${MONGODB_PASSWORD}');
            db.adminCommand('listDatabases');
            quit(0);
        } catch(err) {
            quit(1);
        }"
}

main() {
    log "Starting mongo without auth to verify and then reset credentials..."
    mongod --bind_ip_all --fork --logpath "$LOG_FILE" --noauth
    
    sleep 5
    
    if ! verify_auth; then
        log "Authentication failed with existing credentials - resetting user..."
        mongod --shutdown
        sleep 5
        reset_user
    else
        log "Existing credentials are valid"
        mongod --shutdown
        sleep 5
    fi
    
    log "Starting MongoDB with authentication..."
    exec mongod --bind_ip_all --auth
}

main "$@"