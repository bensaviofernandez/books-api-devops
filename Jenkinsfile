pipeline {
  agent {
    docker {
      image 'docker:24.0.9-cli'
      args '''
        --entrypoint="" \
        --user root \
        -v /var/run/docker.sock:/var/run/docker.sock \
        --network host
      '''
    }
  }

  environment {
    GH_USER    = 'bensaviofernandez'
    REGISTRY   = "ghcr.io/${GH_USER}/books-api"
    IMAGE_TAG  = "${env.BUILD_NUMBER}"
  }

  stages {
    stage('Bootstrap Tools') {
      steps {
        // Install curl so health-check commands work
        sh 'apk update && apk add --no-cache curl'
      }
    }

    stage('Build') {
      steps {
        // Build both test and production images using multi-stage Dockerfile
        sh '''
          docker build --target test -t ${REGISTRY}:test-${IMAGE_TAG} .
          docker build --target production -t ${REGISTRY}:${IMAGE_TAG} .
        '''
      }
    }
    
    stage('Test') {
      steps {
        // Use the test image directly since it's already built with test tools
        sh '''
          docker run --name books-api-test ${REGISTRY}:test-${IMAGE_TAG} \
            pytest -v --junitxml=test-results.xml --cov=app --cov-report=xml
          docker cp books-api-test:/app/test-results.xml .
          docker cp books-api-test:/app/coverage.xml .
          docker rm books-api-test
        '''
        junit 'test-results.xml'
        sh 'grep -A1 testcase test-results.xml'
      }
    }
    
    stage('Code Quality') {
      steps {
        sh '''
          docker run --rm \
            -v "${WORKSPACE}:/usr/src" \
            sonarsource/sonar-scanner-cli:latest \
            -Dsonar.projectKey=books-api \
            -Dsonar.sources=. \
            -Dsonar.host.url=http://host.docker.internal:9000 \
            -Dsonar.login=sqp_b2c843298f821da5e9abc31c5660c300623ccd91 \
            -Dsonar.python.coverage.reportPaths=coverage.xml
          echo "Waiting for SonarQube analysis to complete..."
          sleep 15
          echo "SonarQube analysis completed"
        '''
      }
    }
    
    stage('Security') {
      steps {
        script {
          def image = "${env.REGISTRY}:${env.IMAGE_TAG}"
          def trivyStatus = sh(script: '''
            docker run --rm \
              -v /var/run/docker.sock:/var/run/docker.sock \
              aquasec/trivy:latest image \
                --exit-code 1 \
                --severity HIGH,CRITICAL \
                --ignore-unfixed \
                ${REGISTRY}:${IMAGE_TAG}
          ''', returnStatus: true)
          if (trivyStatus != 0) {
            unstable("⚠️ HIGH/CRITICAL vulnerabilities detected by Trivy")
          }
        }
      }
    }
    
    stage('Push') {
      steps {
        withCredentials([usernamePassword(
          credentialsId: 'github-creds', usernameVariable: 'GH_USER_CRED', passwordVariable: 'GH_PAT')]) {
          sh '''
            echo $GH_PAT | docker login ghcr.io -u $GH_USER_CRED --password-stdin
            docker tag ${REGISTRY}:${IMAGE_TAG} ${REGISTRY}:production
            docker tag ${REGISTRY}:test-${IMAGE_TAG} ${REGISTRY}:test-latest
            docker push ${REGISTRY}:${IMAGE_TAG}
            docker push ${REGISTRY}:production
            docker push ${REGISTRY}:test-${IMAGE_TAG}
            docker push ${REGISTRY}:test-latest
          '''
        }
      }
    }
    
    stage('Deploy to Staging') {
      steps {
        sh '''
          # Create a network for inter-container communication
          docker network create books-api-network || true
          
          # Stop and remove existing container if it exists
          docker stop books-api-staging || true
          docker rm books-api-staging || true
          
          # Run the staging container on the network
          docker run -d --name books-api-staging \
            --network books-api-network \
            -p 5001:5000 \
            ${REGISTRY}:${IMAGE_TAG}
          
          # Wait for container to start
          sleep 5
          
          # Check container is running
          docker ps | grep books-api-staging
          
          # Test API via direct container networking
          docker run --rm --network books-api-network appropriate/curl \
            curl -s http://books-api-staging:5000/books
          
          # Also check using host port
          curl -s http://localhost:5001/books
        '''
      }
    }
    
    stage('Deploy to Production') {
      steps {
        sh '''
          # Stop and remove existing container if it exists
          docker stop books-api-production || true
          docker rm books-api-production || true
          
          # Run the production container on the network
          docker run -d --name books-api-production \
            --network books-api-network \
            -p 5000:5000 \
            --health-cmd="curl -f http://localhost:5000/books || exit 1" \
            --health-interval=10s \
            --health-retries=3 \
            ${REGISTRY}:production
          
          # Wait for container to start and become healthy
          echo "Waiting for container to start..."
          sleep 10
          
          # Show container status
          echo "=== Container status ==="
          docker ps | grep books-api-production
          
          # Test the API endpoint using multiple methods
          echo "=== Testing API with direct curl ==="
          curl -v http://localhost:5000/books || echo "Failed with direct curl"
          
          echo "=== Testing API with Docker network ==="
          docker run --rm --network books-api-network appropriate/curl \
            curl -v http://books-api-production:5000/books || echo "Failed with Docker network"
          
          echo "=== Testing API from inside container ==="
          docker exec books-api-production curl -v http://localhost:5000/books || echo "Failed inside container"
          
          # Show logs
          echo "=== Container logs ==="
          docker logs books-api-production
        '''
      }
      post {
        success {
          echo "🚀 Production deployment successful!"
        }
        failure {
          echo "❌ Production deployment failed!"
        }
      }
    }

    stage('Monitoring') {
      steps {
        sh '''
          # First, add prometheus-client to requirements.txt
          if ! grep -q "prometheus-client" requirements.txt; then
            echo "prometheus-client==0.12.0" >> requirements.txt
          fi
          
          # Create metrics.py if it doesn't exist
          cat > metrics.py << 'EOF'
    from prometheus_client import Counter, Histogram, Gauge, Summary, generate_latest, CONTENT_TYPE_LATEST
    import time
    from flask import request

    # Define metrics
    REQUESTS = Counter('books_api_requests_total', 'Total number of requests to the Books API', ['method', 'endpoint', 'status'])
    IN_PROGRESS = Gauge('books_api_requests_in_progress', 'Number of requests in progress')
    REQUEST_TIME = Summary('books_api_request_duration_seconds', 'Time spent processing request')
    EXCEPTIONS = Counter('books_api_exceptions_total', 'Exceptions caught during request processing')
    DB_OPERATIONS = Counter('books_api_db_operations_total', 'Total database operations', ['operation'])
    BOOKS_COUNT = Gauge('books_api_books_count', 'Number of books in the database')

    # Function to update metrics on API request
    def before_request():
        IN_PROGRESS.inc()
        request.start_time = time.time()

    def after_request(response):
        IN_PROGRESS.dec()
        resp_time = time.time() - request.start_time
        REQUEST_TIME.observe(resp_time)
        REQUESTS.labels(request.method, request.endpoint, response.status_code).inc()
        return response

    def record_exception():
        EXCEPTIONS.inc()

    def update_books_count(count):
        BOOKS_COUNT.set(count)

    def record_db_operation(operation):
        DB_OPERATIONS.labels(operation).inc()
    EOF
          
          # Modify app.py to include metrics
          # This is a bit risky as it depends on app.py structure, but we'll try a basic approach
          if ! grep -q "prometheus_client" app.py; then
            # Create backup
            cp app.py app.py.bak
            
            # Add imports
            sed -i '1s/^/from prometheus_client import generate_latest, CONTENT_TYPE_LATEST\\nfrom metrics import before_request, after_request, record_exception, update_books_count, record_db_operation\\n/' app.py
            
            # Add middleware registration after app initialization
            sed -i '/app = Flask/a app.before_request(before_request)\\napp.after_request(after_request)' app.py
            
            # Add metrics endpoint
            cat >> app.py << 'EOF'

    @app.route('/metrics')
    def metrics():
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
    EOF

            echo "Flask app updated with Prometheus metrics"
          else
            echo "Prometheus metrics already configured in Flask app"
          fi
          
          # Create Prometheus configuration
          cat > prometheus.yml << EOF
    global:
      scrape_interval: 15s
      evaluation_interval: 15s
      scrape_timeout: 10s

    scrape_configs:
      - job_name: 'books-api'
        metrics_path: '/metrics'
        static_configs:
          - targets: ['books-api-production:5000']
        scrape_interval: 5s

      - job_name: 'prometheus'
        static_configs:
          - targets: ['localhost:9090']
    EOF

          # Create alert rules
          mkdir -p rules
          cat > rules/books_api_alerts.yml << EOF
    groups:
    - name: books_api
      rules:
      - alert: BooksApiDown
        expr: up{job="books-api"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Books API is down"
          description: "Books API has been down for more than 1 minute."
      - alert: BooksApiHighResponseTime
        expr: books_api_request_duration_seconds{quantile="0.9"} > 0.5
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Books API high response time"
          description: "Books API has high response time for more than 2 minutes."
    EOF

          # Create docker-compose for monitoring
          cat > docker-compose-monitoring.yml << EOF
    version: '3.8'

    networks:
      books-api-network:
        external: true

    services:
      prometheus:
        image: prom/prometheus:latest
        container_name: books-api-prometheus
        volumes:
          - ./prometheus.yml:/etc/prometheus/prometheus.yml
          - ./rules:/etc/prometheus/rules
        command:
          - '--config.file=/etc/prometheus/prometheus.yml'
          - '--storage.tsdb.path=/prometheus'
          - '--web.console.libraries=/usr/share/prometheus/console_libraries'
          - '--web.console.templates=/usr/share/prometheus/consoles'
        ports:
          - 9090:9090
        networks:
          - books-api-network
        restart: unless-stopped

      grafana:
        image: grafana/grafana:latest
        container_name: books-api-grafana
        volumes:
          - ./grafana/provisioning:/etc/grafana/provisioning
          - ./grafana/dashboards:/var/lib/grafana/dashboards
        environment:
          - GF_SECURITY_ADMIN_USER=admin
          - GF_SECURITY_ADMIN_PASSWORD=admin
          - GF_USERS_ALLOW_SIGN_UP=false
        ports:
          - 3000:3000
        networks:
          - books-api-network
        depends_on:
          - prometheus
        restart: unless-stopped
    EOF

          # Create Grafana dashboard provisioning
          mkdir -p grafana/provisioning/datasources grafana/provisioning/dashboards grafana/dashboards
          
          # Create Prometheus data source
          cat > grafana/provisioning/datasources/prometheus.yml << EOF
    apiVersion: 1

    datasources:
      - name: Prometheus
        type: prometheus
        access: proxy
        url: http://prometheus:9090
        isDefault: true
    EOF

          # Create dashboard provider
          cat > grafana/provisioning/dashboards/provider.yml << EOF
    apiVersion: 1

    providers:
      - name: 'default'
        orgId: 1
        folder: ''
        type: file
        disableDeletion: false
        updateIntervalSeconds: 10
        allowUiUpdates: true
        options:
          path: /var/lib/grafana/dashboards
    EOF

          # Create Books API dashboard
          cat > grafana/dashboards/books_api_dashboard.json << EOF
    {
      "annotations": {
        "list": [
          {
            "builtIn": 1,
            "datasource": "-- Grafana --",
            "enable": true,
            "hide": true,
            "iconColor": "rgba(0, 211, 255, 1)",
            "name": "Annotations & Alerts",
            "target": {
              "limit": 100,
              "matchAny": false,
              "tags": [],
              "type": "dashboard"
            },
            "type": "dashboard"
          }
        ]
      },
      "editable": true,
      "fiscalYearStartMonth": 0,
      "graphTooltip": 0,
      "id": null,
      "links": [],
      "liveNow": false,
      "panels": [
        {
          "datasource": "Prometheus",
          "fieldConfig": {
            "defaults": {
              "color": {
                "mode": "palette-classic"
              },
              "custom": {
                "axisLabel": "",
                "axisPlacement": "auto",
                "barAlignment": 0,
                "drawStyle": "line",
                "fillOpacity": 0.5,
                "gradientMode": "none",
                "hideFrom": {
                  "legend": false,
                  "tooltip": false,
                  "viz": false
                },
                "lineInterpolation": "linear",
                "lineWidth": 1,
                "pointSize": 5,
                "scaleDistribution": {
                  "type": "linear"
                },
                "showPoints": "auto",
                "spanNulls": false,
                "stacking": {
                  "group": "A",
                  "mode": "none"
                },
                "thresholdsStyle": {
                  "mode": "off"
                }
              },
              "mappings": [],
              "thresholds": {
                "mode": "absolute",
                "steps": [
                  {
                    "color": "green",
                    "value": null
                  },
                  {
                    "color": "red",
                    "value": 80
                  }
                ]
              },
              "unit": "short"
            },
            "overrides": []
          },
          "gridPos": {
            "h": 8,
            "w": 12,
            "x": 0,
            "y": 0
          },
          "id": 2,
          "options": {
            "legend": {
              "calcs": [],
              "displayMode": "list",
              "placement": "bottom"
            },
            "tooltip": {
              "mode": "single",
              "sort": "none"
            }
          },
          "targets": [
            {
              "datasource": "Prometheus",
              "expr": "books_api_requests_total",
              "interval": "",
              "legendFormat": "{{method}} {{endpoint}} - {{status}}",
              "refId": "A"
            }
          ],
          "title": "Total Requests",
          "type": "timeseries"
        },
        {
          "datasource": "Prometheus",
          "fieldConfig": {
            "defaults": {
              "color": {
                "mode": "palette-classic"
              },
              "custom": {
                "axisLabel": "",
                "axisPlacement": "auto",
                "barAlignment": 0,
                "drawStyle": "line",
                "fillOpacity": 0.5,
                "gradientMode": "none",
                "hideFrom": {
                  "legend": false,
                  "tooltip": false,
                  "viz": false
                },
                "lineInterpolation": "linear",
                "lineWidth": 1,
                "pointSize": 5,
                "scaleDistribution": {
                  "type": "linear"
                },
                "showPoints": "auto",
                "spanNulls": false,
                "stacking": {
                  "group": "A",
                  "mode": "none"
                },
                "thresholdsStyle": {
                  "mode": "off"
                }
              },
              "mappings": [],
              "thresholds": {
                "mode": "absolute",
                "steps": [
                  {
                    "color": "green",
                    "value": null
                  },
                  {
                    "color": "red",
                    "value": 80
                  }
                ]
              },
              "unit": "s"
            },
            "overrides": []
          },
          "gridPos": {
            "h": 8,
            "w": 12,
            "x": 12,
            "y": 0
          },
          "id": 4,
          "options": {
            "legend": {
              "calcs": [],
              "displayMode": "list",
              "placement": "bottom"
            },
            "tooltip": {
              "mode": "single",
              "sort": "none"
            }
          },
          "targets": [
            {
              "datasource": "Prometheus",
              "expr": "books_api_request_duration_seconds",
              "interval": "",
              "legendFormat": "Request Duration",
              "refId": "A"
            }
          ],
          "title": "Request Duration",
          "type": "timeseries"
        },
        {
          "datasource": "Prometheus",
          "fieldConfig": {
            "defaults": {
              "color": {
                "mode": "thresholds"
              },
              "mappings": [],
              "thresholds": {
                "mode": "absolute",
                "steps": [
                  {
                    "color": "green",
                    "value": null
                  },
                  {
                    "color": "red",
                    "value": 80
                  }
                ]
              }
            },
            "overrides": []
          },
          "gridPos": {
            "h": 8,
            "w": 12,
            "x": 0,
            "y": 8
          },
          "id": 6,
          "options": {
            "colorMode": "value",
            "graphMode": "area",
            "justifyMode": "auto",
            "orientation": "auto",
            "reduceOptions": {
              "calcs": [
                "lastNotNull"
              ],
              "fields": "",
              "values": false
            },
            "textMode": "auto"
          },
          "pluginVersion": "8.5.0",
          "targets": [
            {
              "datasource": "Prometheus",
              "expr": "books_api_books_count",
              "interval": "",
              "legendFormat": "Books Count",
              "refId": "A"
            }
          ],
          "title": "Number of Books",
          "type": "stat"
        },
        {
          "datasource": "Prometheus",
          "fieldConfig": {
            "defaults": {
              "color": {
                "mode": "palette-classic"
              },
              "custom": {
                "axisLabel": "",
                "axisPlacement": "auto",
                "barAlignment": 0,
                "drawStyle": "line",
                "fillOpacity": 0.5,
                "gradientMode": "none",
                "hideFrom": {
                  "legend": false,
                  "tooltip": false,
                  "viz": false
                },
                "lineInterpolation": "linear",
                "lineWidth": 1,
                "pointSize": 5,
                "scaleDistribution": {
                  "type": "linear"
                },
                "showPoints": "auto",
                "spanNulls": false,
                "stacking": {
                  "group": "A",
                  "mode": "none"
                },
                "thresholdsStyle": {
                  "mode": "off"
                }
              },
              "mappings": [],
              "thresholds": {
                "mode": "absolute",
                "steps": [
                  {
                    "color": "green",
                    "value": null
                  },
                  {
                    "color": "red",
                    "value": 80
                  }
                ]
              }
            },
            "overrides": []
          },
          "gridPos": {
            "h": 8,
            "w": 12,
            "x": 12,
            "y": 8
          },
          "id": 8,
          "options": {
            "legend": {
              "calcs": [],
              "displayMode": "list",
              "placement": "bottom"
            },
            "tooltip": {
              "mode": "single",
              "sort": "none"
            }
          },
          "targets": [
            {
              "datasource": "Prometheus",
              "expr": "books_api_db_operations_total",
              "interval": "",
              "legendFormat": "{{operation}}",
              "refId": "A"
            }
          ],
          "title": "Database Operations",
          "type": "timeseries"
        }
      ],
      "refresh": "5s",
      "schemaVersion": 35,
      "style": "dark",
      "tags": [],
      "templating": {
        "list": []
      },
      "time": {
        "from": "now-1h",
        "to": "now"
      },
      "timepicker": {},
      "timezone": "",
      "title": "Books API Dashboard",
      "version": 1
    }
    EOF

          # Deploy monitoring stack
          echo "Starting Prometheus and Grafana monitoring stack"
          docker-compose -f docker-compose-monitoring.yml up -d

          # Wait for monitoring stack to be ready
          echo "Waiting for monitoring services to start..."
          sleep 10
          
          # Check services are running
          docker container ls | grep prometheus
          docker container ls | grep grafana
          
          echo "✅ Monitoring setup complete!"
          echo "- Prometheus is available at http://localhost:9090"
          echo "- Grafana is available at http://localhost:3000 (admin/admin)"
          echo "- Books API metrics are available at http://localhost:5000/metrics"
        '''
        archiveArtifacts artifacts: 'prometheus.yml,rules/*.yml,docker-compose-monitoring.yml,grafana/provisioning/**/*,grafana/dashboards/**/*,metrics.py', fingerprint: true
      }
    }
  }


  post {
    always { 
      sh '''
        # Don't prune everything - keep the production container running
        docker image prune -f
        # Remove test containers
        docker rm books-api-test || true
        docker rm books-api-staging || true
      '''
    }
    success { echo "Pipeline completed successfully!" }
    failure { echo "Pipeline failed!" }
  }
}
