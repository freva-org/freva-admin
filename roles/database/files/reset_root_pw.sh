#!/bin/bash
set -e

mysql -u root -v <<EOF
USE mysql;
FLUSH PRIVILEGES;

-- Ensure the database exists
CREATE DATABASE IF NOT EXISTS \`$MYSQL_DATABASE\`;

-- Ensure the root user exists
CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY '$MYSQL_ROOT_PASSWORD';
ALTER USER 'root'@'localhost' IDENTIFIED BY '$MYSQL_ROOT_PASSWORD';

-- Ensure the application user exists and has privileges on the database
DROP USER IF EXISTS '$MYSQL_USER'@'%';
CREATE USER '$MYSQL_USER'@'%' IDENTIFIED BY '$MYSQL_PASSWORD';
GRANT ALL PRIVILEGES ON \`$MYSQL_DATABASE\`.* TO '$MYSQL_USER'@'%';

-- Root privileges
GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost' WITH GRANT OPTION;
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;

FLUSH PRIVILEGES;
EOF
