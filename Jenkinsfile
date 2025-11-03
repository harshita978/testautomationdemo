pipeline {
  agent any

  options {
    timeout(time: 30, unit: 'MINUTES')
    timestamps()
  }

  stages {
    stage('Checkout') {
      steps {
        // If your default branch is main:
        git branch: 'main', url: 'https://github.com/harshita978/testautomationdemo.git'
        bat 'git --version'
      }
    }

    stage('Build') {
      steps {
        bat 'echo Building...'
      }
    }

    stage('Test') {
      steps {
        bat 'echo Running tests...'
        // If you later output JUnit XML, publish with: junit 'reports/**/*.xml'
      }
    }

    stage('Archive') {
      steps {
        archiveArtifacts artifacts: 'dist/**, build/**, target/**', onlyIfSuccessful: true
      }
    }
  }

  post {
    always {
      echo "Pipeline finished with status: ${currentBuild.currentResult}"
    }
  }
}
