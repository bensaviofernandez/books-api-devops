pipeline {
  agent {
    docker {
      image 'docker:24.0.9-cli'
      args  '-v /var/run/docker.sock:/var/run/docker.sock'
    }
  }

  environment {
    IMAGE_REPO = "ghcr.io/${env.GITHUB_ACTOR.toLowerCase()}/books-api"
    IMAGE_TAG  = "${env.BUILD_NUMBER}"
  }

  stages {
    stage('Build image') {
      steps {
        sh 'docker build -t $IMAGE_REPO:$IMAGE_TAG .'
      }
    }

    stage('Push image') {
      steps {
        withCredentials([usernamePassword(
          credentialsId: 'github-creds',
          usernameVariable: 'GH_USER',
          passwordVariable: 'GH_PAT'
        )]) {
          sh '''
            echo $GH_PAT | docker login ghcr.io -u $GH_USER --password-stdin
            docker push $IMAGE_REPO:$IMAGE_TAG
          '''
        }
      }
    }
  }

  post {
    always { sh 'docker system prune -af' }   // keep Jenkins disk light
  }
}
