pipeline {
  agent any

  options {
    timeout(time: 30, unit: 'MINUTES')
    timestamps()
    skipDefaultCheckout(true)
  }

  environment {
    // Fast defaults your script can read (optional)
    WAIT_TIMEOUT = '3000'
    NAV_TIMEOUT  = '7000'
    SCREENSHOT_EVERY_ACTION   = 'false'
    SCREENSHOT_ON_FAILURE     = 'true'
    SCREENSHOT_ON_SUCCESS_END = 'false'
    FULL_PAGE_SHOTS           = 'false'
    START_URL = '' // set if you want to override inside CI
    PYTHONDONTWRITEBYTECODE = '1'
    PYTHONUNBUFFERED        = '1'
  }

  stages {
    stage('Checkout') {
      steps {
        // Ensure Git is on PATH (adjust path if your Git is elsewhere)
        withEnv(['PATH+GIT=C:\\Program Files\\Git\\bin']) {
          checkout([$class: 'GitSCM',
            branches: [[name: '*/main']],
            userRemoteConfigs: [[
              url: 'https://github.com/harshita978/testautomationdemo.git',
              credentialsId: 'github-pat' // remove if repo is public
            ]]
          ])
          bat 'git --version'
        }
      }
    }

    stage('Detect project folder') {
      steps {
        // Figure out where runtest_data_driven_template.py lives (root vs subfolder)
        bat '''
          setlocal EnableDelayedExpansion
          if exist runtest_data_driven_template.py (
            set RUN_DIR=.
          ) else if exist test-automation-demo\\runtest_data_driven_template.py (
            set RUN_DIR=test-automation-demo
          ) else (
            echo ERROR: Could not find runtest_data_driven_template.py
            exit /b 1
          )
          echo RUN_DIR=!RUN_DIR!> run_dir.txt
        '''
      }
    }

    stage('Setup Python & Playwright') {
      steps {
        // If Python isn't on PATH for the Jenkins service, add it here:
        // withEnv(['PATH+PY=C:\\Python311;C:\\Python311\\Scripts']) { ... }
        bat '''
          for /f "usebackq delims=" %%A in ("run_dir.txt") do set %%A
          echo Using RUN_DIR=%RUN_DIR%

          python -V
          python -m pip install -U pip setuptools wheel

          if exist %RUN_DIR%\\requirements.txt (
            python -m pip install -r %RUN_DIR%\\requirements.txt
          ) else (
            python -m pip install playwright reportlab matplotlib
          )

          rem Install browsers (Windows: no --with-deps)
          python -m playwright install
        '''
      }
    }

    stage('Run tests') {
      steps {
        bat '''
          for /f "usebackq delims=" %%A in ("run_dir.txt") do set %%A
          echo Running in %RUN_DIR%
          cd /d %RUN_DIR%
          python runtest_data_driven_template.py
        '''
      }
    }

    stage('Archive Reports') {
      steps {
        // Try both possible locations; allow empty to avoid failing archive if path differs
        archiveArtifacts artifacts: 'dd_reports/**', allowEmptyArchive: true, onlyIfSuccessful: false
        archiveArtifacts artifacts: 'test-automation-demo/dd_reports/**', allowEmptyArchive: true, onlyIfSuccessful: false
      }
    }
  }

  post {
    always {
      echo "Pipeline finished with status: ${currentBuild.currentResult}"
    }
  }
}
