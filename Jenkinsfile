pipeline {
  agent {
    docker {
      image 'docker:24.0.9-cli'
      args  '-v /var/run/docker.sock:/var/run/docker.sock'
    }
  }

  environment {
    GH_USER    = 'bensaviofernandez'
    REGISTRY   = "ghcr.io/${GH_USER}/books-api"
    IMAGE_TAG  = "${env.BUILD_NUMBER}"
  }

  stages {
    stage('Build') {
      steps {
        sh 'docker build -t $REGISTRY:$IMAGE_TAG .'
      }
    }
    
    stage('Test') {
      steps {
        sh '''
          cat > Dockerfile.test << EOF
FROM $REGISTRY:$IMAGE_TAG
RUN pip install pytest pytest-cov
WORKDIR /app
EOF
          docker build -t $REGISTRY:test-$IMAGE_TAG -f Dockerfile.test .
          docker run --name books-api-test $REGISTRY:test-$IMAGE_TAG \
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
          def trivyStatus = sh(
            script: """
              docker run --rm \\
                -v /var/run/docker.sock:/var/run/docker.sock \\
                aquasec/trivy:latest image \\
                  --exit-code 1 \\
                  --severity HIGH,CRITICAL \\
                  --ignore-unfixed \\
                  ${image}
            """,
            returnStatus: true
          )
          if (trivyStatus != 0) {
            unstable("⚠️ HIGH/CRITICAL vulnerabilities detected by Trivy")
          }
        }
      }
      post {
        unstable {
          echo "Security stage detected high/critical vulnerabilities. Please triage."
        }
      }
    }

    stage('Integration') {
      steps {
        sh '''
          cat > docker-compose.test.yml << EOF
version: '3'
services:
  api:
    image: ${REGISTRY}:${IMAGE_TAG}
    ports:
      - "5000:5000"
  test:
    image: curlimages/curl:latest
    command: /bin/sh -c "sleep 5 && curl -f http://api:5000/books"
    depends_on:
      - api
EOF
          docker-compose -f docker-compose.test.yml up --abort-on-container-exit
          docker-compose -f docker-compose.test.yml down
        '''
      }
    }
    
    stage('Push') {
      steps {
        withCredentials([usernamePassword(
          credentialsId: 'github-creds',
          usernameVariable: 'GH_USER_CRED',
          passwordVariable: 'GH_PAT'
        )]) {
          sh '''
            echo $GH_PAT | docker login ghcr.io -u $GH_USER_CRED --password-stdin
            docker push $REGISTRY:$IMAGE_TAG
          '''
        }
      }
    }

    stage('Deploy (Staging)') {
      steps {
        sh '''
          # 1) Create a staging compose file
          cat > docker-compose.staging.yml << EOF
          version: '3.8'
          services:
          books-api:
          image: ${REGISTRY}:${IMAGE_TAG}
          ports:
          - "4000:5000"
          healthcheck:
          test: ["CMD", "curl", "-f", "http://localhost:5000/health || exit 1"]
          interval: 10s
          retries: 5
          EOF

          # 2) Start staging (detached + rebuild)
          docker-compose -f docker-compose.staging.yml up -d --build

          # 3) Grab the container ID for the books-api service
          CID=$(docker-compose -f docker-compose.staging.yml ps -q books-api)
          if [ -z "$CID" ]; then
            echo "❌ Could not find the books-api container"
            exit 1
          fi

          # 4) Wait until it's healthy
          until [ "$(docker inspect -f '{{.State.Health.Status}}' $CID)" = "healthy" ]; do
            echo "Waiting for $CID to become healthy…"
            sleep 5
          done

          echo "✅ Staging deployment is healthy on port 4000"
        '''
      }
      post {
        success { echo "Deploy (Staging) succeeded" }
        failure {
          echo "❌ Deploy (Staging) failed — dumping logs"
          sh 'docker-compose -f docker-compose.staging.yml logs'
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
    always { sh 'docker system prune -af' }
    success { echo "Pipeline completed successfully!" }
    failure { echo "Pipeline failed!" }
  }
}
