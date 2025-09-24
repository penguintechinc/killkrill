#!/bin/bash
# KillKrill Elasticsearch Setup Script
# Configures Elasticsearch for optimal performance and caching

set -e

ELASTICSEARCH_HOST="${ELASTICSEARCH_HOST:-localhost:9200}"
INDEX_PREFIX="${ELASTICSEARCH_INDEX_PREFIX:-killkrill}"

echo "🔧 Setting up Elasticsearch for KillKrill..."

# Wait for Elasticsearch to be ready
echo "⏳ Waiting for Elasticsearch to be ready..."
until curl -s "$ELASTICSEARCH_HOST/_cluster/health" | grep -q '"status":"yellow\|green"'; do
    echo "Waiting for Elasticsearch..."
    sleep 5
done

echo "✅ Elasticsearch is ready!"

# Set cluster-wide settings for performance
echo "🚀 Applying performance settings..."
curl -X PUT "$ELASTICSEARCH_HOST/_cluster/settings" \
    -H "Content-Type: application/json" \
    -d '{
        "persistent": {
            "indices.queries.cache.size": "10%",
            "indices.requests.cache.size": "2%",
            "indices.requests.cache.expire": "5m",
            "indices.fielddata.cache.size": "20%",
            "indices.memory.index_buffer_size": "30%",
            "cluster.routing.allocation.disk.threshold.enabled": true,
            "cluster.routing.allocation.disk.watermark.low": "85%",
            "cluster.routing.allocation.disk.watermark.high": "90%",
            "cluster.routing.allocation.disk.watermark.flood_stage": "95%",
            "search.max_buckets": 65536,
            "indices.breaker.total.limit": "70%",
            "indices.breaker.fielddata.limit": "40%",
            "indices.breaker.request.limit": "40%"
        }
    }'

echo "✅ Performance settings applied!"

# Create index template for logs
echo "📋 Creating index template for logs..."
curl -X PUT "$ELASTICSEARCH_HOST/_index_template/killkrill-logs" \
    -H "Content-Type: application/json" \
    -d @infrastructure/monitoring/logstash/templates/killkrill-logs.json

echo "✅ Index template created!"

# Create Index Lifecycle Management policy
echo "🔄 Creating ILM policy for log rotation..."
curl -X PUT "$ELASTICSEARCH_HOST/_ilm/policy/killkrill-logs-policy" \
    -H "Content-Type: application/json" \
    -d '{
        "policy": {
            "phases": {
                "hot": {
                    "min_age": "0ms",
                    "actions": {
                        "rollover": {
                            "max_size": "50gb",
                            "max_age": "1d",
                            "max_docs": 100000000
                        },
                        "set_priority": {
                            "priority": 100
                        }
                    }
                },
                "warm": {
                    "min_age": "7d",
                    "actions": {
                        "set_priority": {
                            "priority": 50
                        },
                        "allocate": {
                            "number_of_replicas": 0
                        },
                        "forcemerge": {
                            "max_num_segments": 1
                        }
                    }
                },
                "cold": {
                    "min_age": "30d",
                    "actions": {
                        "set_priority": {
                            "priority": 0
                        },
                        "allocate": {
                            "number_of_replicas": 0
                        }
                    }
                },
                "delete": {
                    "min_age": "90d",
                    "actions": {
                        "delete": {}
                    }
                }
            }
        }
    }'

echo "✅ ILM policy created!"

# Create initial index with alias
echo "📦 Creating initial index..."
curl -X PUT "$ELASTICSEARCH_HOST/$INDEX_PREFIX-logs-$(date +%Y.%m.%d)-000001" \
    -H "Content-Type: application/json" \
    -d '{
        "settings": {
            "index.lifecycle.name": "killkrill-logs-policy",
            "index.lifecycle.rollover_alias": "killkrill-logs-write",
            "index.number_of_shards": 1,
            "index.number_of_replicas": 0,
            "index.codec": "best_compression",
            "index.refresh_interval": "5s",
            "index.queries.cache.enabled": true,
            "index.requests.cache.enable": true
        }
    }'

# Create write alias
curl -X POST "$ELASTICSEARCH_HOST/_aliases" \
    -H "Content-Type: application/json" \
    -d '{
        "actions": [
            {
                "add": {
                    "index": "'$INDEX_PREFIX'-logs-'$(date +%Y.%m.%d)'-000001",
                    "alias": "killkrill-logs-write",
                    "is_write_index": true
                }
            }
        ]
    }'

echo "✅ Initial index and alias created!"

# Create search templates for common queries
echo "🔍 Creating search templates..."

# Template for service logs
curl -X PUT "$ELASTICSEARCH_HOST/_scripts/service-logs-template" \
    -H "Content-Type: application/json" \
    -d '{
        "script": {
            "lang": "mustache",
            "source": {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "term": {
                                    "service.name": "{{service_name}}"
                                }
                            },
                            {
                                "range": {
                                    "@timestamp": {
                                        "gte": "{{start_time}}",
                                        "lte": "{{end_time}}"
                                    }
                                }
                            }
                        ],
                        "filter": [
                            {{#log_level}}
                            {
                                "term": {
                                    "log.level": "{{log_level}}"
                                }
                            }
                            {{/log_level}}
                        ]
                    }
                },
                "sort": [
                    {
                        "@timestamp": {
                            "order": "desc"
                        }
                    }
                ],
                "size": "{{size}}",
                "from": "{{from}}"
            }
        }
    }'

# Template for error logs
curl -X PUT "$ELASTICSEARCH_HOST/_scripts/error-logs-template" \
    -H "Content-Type: application/json" \
    -d '{
        "script": {
            "lang": "mustache",
            "source": {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "terms": {
                                    "log.level": ["error", "critical", "fatal", "emergency"]
                                }
                            },
                            {
                                "range": {
                                    "@timestamp": {
                                        "gte": "{{start_time}}",
                                        "lte": "{{end_time}}"
                                    }
                                }
                            }
                        ]
                    }
                },
                "sort": [
                    {
                        "@timestamp": {
                            "order": "desc"
                        }
                    }
                ],
                "size": "{{size}}",
                "from": "{{from}}"
            }
        }
    }'

echo "✅ Search templates created!"

# Optimize indices for search performance
echo "⚡ Optimizing indices..."
curl -X POST "$ELASTICSEARCH_HOST/$INDEX_PREFIX-logs-*/_forcemerge?max_num_segments=1&wait_for_completion=false"

echo "✅ Index optimization started!"

# Create monitoring aliases
echo "📊 Creating monitoring aliases..."
curl -X POST "$ELASTICSEARCH_HOST/_aliases" \
    -H "Content-Type: application/json" \
    -d '{
        "actions": [
            {
                "add": {
                    "index": "'$INDEX_PREFIX'-logs-*",
                    "alias": "killkrill-logs-all",
                    "filter": {
                        "range": {
                            "@timestamp": {
                                "gte": "now-30d"
                            }
                        }
                    }
                }
            },
            {
                "add": {
                    "index": "'$INDEX_PREFIX'-logs-*",
                    "alias": "killkrill-logs-recent",
                    "filter": {
                        "range": {
                            "@timestamp": {
                                "gte": "now-7d"
                            }
                        }
                    }
                }
            }
        ]
    }'

echo "✅ Monitoring aliases created!"

# Enable slow query logging for performance monitoring
echo "🐌 Enabling slow query logging..."
curl -X PUT "$ELASTICSEARCH_HOST/$INDEX_PREFIX-logs-*/_settings" \
    -H "Content-Type: application/json" \
    -d '{
        "index.search.slowlog.threshold.query.warn": "10s",
        "index.search.slowlog.threshold.query.info": "5s",
        "index.search.slowlog.threshold.query.debug": "2s",
        "index.search.slowlog.threshold.query.trace": "500ms",
        "index.search.slowlog.threshold.fetch.warn": "1s",
        "index.search.slowlog.threshold.fetch.info": "800ms",
        "index.search.slowlog.threshold.fetch.debug": "500ms",
        "index.search.slowlog.threshold.fetch.trace": "200ms"
    }'

echo "✅ Slow query logging enabled!"

echo ""
echo "🎉 Elasticsearch setup complete!"
echo ""
echo "📊 Cluster Status:"
curl -s "$ELASTICSEARCH_HOST/_cluster/health?pretty"
echo ""
echo "📋 Indices:"
curl -s "$ELASTICSEARCH_HOST/_cat/indices/$INDEX_PREFIX-*?v"
echo ""
echo "🔗 Aliases:"
curl -s "$ELASTICSEARCH_HOST/_cat/aliases/killkrill-*?v"