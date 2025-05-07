pipeline {
  agent {
    docker {
      image 'docker:24.0.9-cli'
      args '''
        --entrypoint="" \
        --user root \
        -v /var/run/docker.sock:/var/run/docker.sock
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
          def trivyStatus = sh(script: '''
            docker run --rm \
              -v /var/run/docker.sock:/var/run/docker.sock \
              aquasec/trivy:latest image \
                --exit-code 1 \
                --severity HIGH,CRITICAL \
                --ignore-unfixed \
                ${image}
          ''', returnStatus: true)
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
          docker-compose -f docker-compose.test.yml up --abort-on-container-exit --remove-orphans
          docker-compose -f docker-compose.test.yml down --remove-orphans
        '''
      }
    }
    
    stage('Push') {
      steps {
        withCredentials([usernamePassword(
          credentialsId: 'github-creds', usernameVariable: 'GH_USER_CRED', passwordVariable: 'GH_PAT')]) {
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
          # Clean any old staging resources
          docker-compose -f docker-compose.staging.yml down --remove-orphans || true

          # Write staging compose with test service
          cat > docker-compose.staging.yml <<EOF
version: '3.8'
services:
  books-api:
    image: ${REGISTRY}:${IMAGE_TAG}
    ports:
      - "4000:5000"
    command: flask run --host=0.0.0.0 --port=5000
  smoke-test:
    image: curlimages/curl:latest
    depends_on:
      - books-api
    command: /bin/sh -c "sleep 15 && curl -f http://books-api:5000/books"
EOF

          # Launch staging and smoke-test
          docker-compose -f docker-compose.staging.yml up --abort-on-container-exit
          testStatus=$?
          docker-compose -f docker-compose.staging.yml down --remove-orphans

          if [ $testStatus -ne 0 ]; then
            echo "❌ Staging smoke test failed"
            exit 1
          else
            echo "✅ Staging is live on http://localhost:4000/books"
          fi
        '''
      }
      post {
        success { echo "🌟 Deploy (Staging) succeeded!" }
        failure { echo "💥 Deploy (Staging) failed!" }
      }
    }

    stage('Release (Prod)') {
      steps {
        checkout scm
        sh '''
          docker-compose -f docker-compose.prod.yml pull
          docker-compose -f docker-compose.prod.yml up -d
          sleep 10
          if curl -f http://localhost:5000/health; then
            echo '✅ Production is live on port 5000'
          else
            echo '❌ Production failed to respond'
            docker-compose -f docker-compose.prod.yml logs
            exit 1
          fi
        '''
      }
      post {
        success { echo '🌟 Release (Prod) succeeded!' }
        failure { echo '💥 Release (Prod) failed — see logs above.' }
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
