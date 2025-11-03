pipeline {
  agent any

  options {
    timeout(time: 30, unit: 'MINUTES')
    timestamps()
    skipDefaultCheckout(true)   // Jenkins won't auto-checkout; we do it below
  }

  stages {
    stage('Checkout') {
      steps {
        // Add Git to PATH only for this block (matches your install path)
        withEnv(['PATH+GIT=C:\\Program Files\\Git\\bin']) {
          checkout([$class: 'GitSCM',
            branches: [[name: '*/main']],
            userRemoteConfigs: [[
              url: 'https://github.com/harshita978/testautomationdemo.git',
              // If your repo is PUBLIC, you can remove the next line
              credentialsId: 'github-pat'
            ]]
          ])
          bat 'git --version'
        }
      }
    }

    stage('Build') {
      steps {
        bat 'echo Building...'
        // e.g., bat 'mvn -B -DskipTests package'
      }
    }

    stage('Test') {
      steps {
        bat 'echo Running tests...'
        // e.g., bat 'pytest -q'
        // If you generate JUnit XML, publish with: junit 'reports/**/*.xml'
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
