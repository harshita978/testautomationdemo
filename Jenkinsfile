pipeline {
  agent any

  options {
    timeout(time: 30, unit: 'MINUTES')
    timestamps()
    skipDefaultCheckout(true)
  }

  stages {
    stage('Checkout') {
      steps {
        withEnv(['PATH+GIT=C:\\Program Files\\Git\\bin']) {
          checkout([$class: 'GitSCM',
            branches: [[name: '*/main']],
            userRemoteConfigs: [[
              url: 'https://github.com/harshita978/testautomationdemo.git',
              // Remove credentialsId line if repo is public
              credentialsId: 'github-pat'
            ]]
          ])
          bat 'git --version'
        }
      }
    }

    stage('Build') {
      steps {
        bat '''
          echo Building...
          if not exist build mkdir build
          echo Demo artifact from Jenkins > build\\artifact.txt
        '''
      }
    }

    stage('Test') {
      steps {
        bat 'echo Running tests...'
        // If you later emit JUnit XML, publish with: junit 'reports/**/*.xml'
      }
    }

    stage('Archive') {
      steps {
        // We created build\\artifact.txt above, so this will succeed
        archiveArtifacts artifacts: 'build/**', onlyIfSuccessful: true
        // If you prefer to never fail when empty, use:
        // archiveArtifacts artifacts: 'dist/**, build/**, target/**', allowEmptyArchive: true, onlyIfSuccessful: true
      }
    }
  }

  post {
    always {
      echo "Pipeline finished with status: ${currentBuild.currentResult}"
    }
  }
}
