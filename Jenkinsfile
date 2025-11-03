pipeline {
  agent any

  options {
    timeout(time: 30, unit: 'MINUTES')
    ansiColor('xterm')
  }

  tools {
    git 'DefaultGit'   // matches the name you set in Global Tool Configuration
  }

  environment {
    // add anything you need here, e.g. TEST_ENV = 'dev'
  }

  stages {
    stage('Checkout') {
      steps {
        checkout([
          $class: 'GitSCM',
          branches: [[name: '*/main']],
          userRemoteConfigs: [[
            url: 'https://github.com/<your-username>/<repo>.git',
            // remove the next line if your repo is public
            credentialsId: 'github-pat'
          ]]
        ])
        bat 'git --version'
      }
    }

    stage('Build') {
      steps {
        bat 'echo Building...'
        // bat 'mvn -B -DskipTests package'   // example for Maven
      }
    }

    stage('Test') {
      steps {
        bat 'echo Running tests...'
        // bat 'pytest -q'                    // example for Python
        // junit 'reports/**/*.xml'           // publish results if you produce JUnit XML
      }
    }

    stage('Archive') {
      steps {
        archiveArtifacts artifacts: 'dist/**, build/**, target/**/*.jar', onlyIfSuccessful: true
      }
    }
  }

  post {
    always {
      echo "Pipeline finished with status: ${currentBuild.currentResult}"
    }
  }
}
