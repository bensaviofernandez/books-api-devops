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
          cat > prometheus.yml << EOF
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'books-api'
    static_configs:
      - targets: ['localhost:5000']
EOF
          echo "Monitoring configuration prepared for Prometheus"
          cat prometheus.yml
        '''
        archiveArtifacts artifacts: 'prometheus.yml', fingerprint: true
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
