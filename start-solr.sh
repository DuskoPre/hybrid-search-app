#!/bin/bash
set -e

export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export SOLR_HOME=/var/solr
export SOLR_LOGS_DIR=/var/solr/logs

echo "🚀 Starting Solr..."

# Start Solr in foreground mode
cd /opt/solr
exec sudo -u solr bin/solr start -f -p 8983 -s /var/solr/data
