pipeline {
  agent any      // runs on your Windows Jenkins controller

  options { timeout(time: 30, unit: 'MINUTES') }

  environment {
    WAIT_TIMEOUT = '3000'
    NAV_TIMEOUT  = '7000'
    SCREENSHOT_EVERY_ACTION   = 'false'
    SCREENSHOT_ON_FAILURE     = 'true'
    SCREENSHOT_ON_SUCCESS_END = 'false'
    FULL_PAGE_SHOTS           = 'false'
    START_URL = ''            // optional override

    PYTHONDONTWRITEBYTECODE = '1'
    PYTHONUNBUFFERED = '1'
  }

  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Setup Python & Playwright') {
      steps {
        powershell '''
          python -V
          python -m pip install -U pip setuptools wheel
          python -m pip install -r test-automation-demo/requirements.txt
          python -m playwright install
        '''
      }
    }

    stage('Run tests') {
      steps {
        dir('test-automation-demo') {
          powershell 'python runtest_data_driven_template.py'
        }
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: 'test-automation-demo/dd_reports/**', fingerprint: true
    }
  }
}
