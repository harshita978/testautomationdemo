pipeline {
  agent any

  options {
    timeout(time: 30, unit: 'MINUTES')
    timestamps()
    skipDefaultCheckout(true)
  }

  environment {
    // ---- Tunables your test/app can read ----
    WAIT_TIMEOUT_MS           = '30000'   // how long to wait for app readiness
    NAV_TIMEOUT               = '7000'
    SCREENSHOT_EVERY_ACTION   = 'false'
    SCREENSHOT_ON_FAILURE     = 'true'
    SCREENSHOT_ON_SUCCESS_END = 'false'
    FULL_PAGE_SHOTS           = 'false'
    START_URL                 = 'http://127.0.0.1:5000'  // app base URL
    PYTHONDONTWRITEBYTECODE   = '1'
    PYTHONUNBUFFERED          = '1'

    // ---- Paths ----
    APP_DIR                   = 'oracle_demo'           // where app.py lives
    REPORT_DIR                = 'dd_reports'            // where tests write reports

    // ---- Tools (adjust if Python lives elsewhere) ----
    PY                        = 'python'
  }

  stages {
    stage('Checkout') {
      steps {
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

    stage('Detect project layout') {
      steps {
        bat '''
          setlocal EnableDelayedExpansion
          set RUN_DIR=
          set RUNNER=

          if exist runtest_data_driven_template.py (
            set RUN_DIR=.
            set RUNNER=runtest_data_driven_template.py
          ) else if exist runtest_data_driven_template_siebel_v2.py (
            set RUN_DIR=.
            set RUNNER=runtest_data_driven_template_siebel_v2.py
          ) else if exist test-automation-demo\\runtest_data_driven_template.py (
            set RUN_DIR=test-automation-demo
            set RUNNER=runtest_data_driven_template.py
          ) else if exist test-automation-demo\\runtest_data_driven_template_siebel_v2.py (
            set RUN_DIR=test-automation-demo
            set RUNNER=runtest_data_driven_template_siebel_v2.py
          ) else (
            echo ERROR: Could not find a test runner (runtest_data_driven_template*.py)
            exit /b 1
          )

          echo RUN_DIR=!RUN_DIR!> run_dir.txt
          echo RUNNER=!RUNNER!> runner.txt

          if not exist "%APP_DIR%\\app.py" (
            echo ERROR: Expected app at "%APP_DIR%\\app.py" but not found.
            exit /b 1
          )
        '''
      }
    }

    stage('Setup Python & Playwright') {
      steps {
        bat '''
          for /f "usebackq delims=" %%A in ("run_dir.txt") do set RUN_DIR=%%A
          echo Using RUN_DIR=%RUN_DIR%

          "%PY%" -V
          "%PY%" -m pip install -U pip setuptools wheel

          if exist "%RUN_DIR%\\requirements.txt" (
            "%PY%" -m pip install -r "%RUN_DIR%\\requirements.txt"
          ) else (
            "%PY%" -m pip install playwright reportlab matplotlib
          )

          if exist "%APP_DIR%\\requirements.txt" (
            "%PY%" -m pip install -r "%APP_DIR%\\requirements.txt"
          )

          "%PY%" -m playwright install
        '''
      }
    }

    stage('Start App (background)') {
      steps {
        bat '''
          powershell -NoProfile -ExecutionPolicy Bypass ^
            "$p = Start-Process -FilePath '%PY%' -ArgumentList 'app.py' -WorkingDirectory '%APP_DIR%' -PassThru; ^
             $p.Id | Out-File -FilePath app_pid.txt -Encoding ascii; ^
             Write-Host ('App PID: ' + $p.Id)"

          rem Wait until %START_URL% responds (up to WAIT_TIMEOUT_MS)
          powershell -NoProfile -ExecutionPolicy Bypass ^
            "$deadline = (Get-Date).AddMilliseconds([int]$env:WAIT_TIMEOUT_MS); ^
             while ((Get-Date) -lt $deadline) { ^
               try { Invoke-WebRequest -Uri '%START_URL%/' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } ^
               catch { Start-Sleep -Milliseconds 500 } ^
             }; exit 1"
          if errorlevel 1 (
            echo ERROR: App did not become ready on %START_URL% within %WAIT_TIMEOUT_MS% ms
            type app_pid.txt
            exit /b 1
          )
          echo App is up at %START_URL%
        '''
      }
    }

    stage('Run Tests') {
      steps {
        script {
          def rc = bat(
            returnStatus: true,
            label: 'Execute data-driven tests',
            script: '''
              for /f "usebackq delims=" %%A in ("run_dir.txt") do set RUN_DIR=%%A
              for /f "usebackq delims=" %%A in ("runner.txt") do set RUNNER=%%A

              echo Running %%RUNNER%% in %%RUN_DIR%%
              cd /d "%%RUN_DIR%%"

              "%PY%" "%%RUNNER%%"
              set TEST_RC=%ERRORLEVEL%
              echo Test runner exit code: %TEST_RC%
              exit /b %TEST_RC%
            '''
          )
          echo "Test runner exit code: ${rc}"
          if (rc != 0) {
            currentBuild.result = 'UNSTABLE'  // keep pipeline going to archive
          }
        }
      }
    }

    stage('Summarize (latest run)') {
      steps {
        bat '''
          if not exist "%REPORT_DIR%" (
            echo No %REPORT_DIR% directory found (maybe runner wrote elsewhere)
          ) else (
            for /f "delims=" %%i in ('dir /ad /b "%REPORT_DIR%" ^| sort') do set LAST=%%i
            if defined LAST (
              echo Latest report folder: %REPORT_DIR%\\%LAST%
              if exist "%REPORT_DIR%\\%LAST%\\results.txt" type "%REPORT_DIR%\\%LAST%\\results.txt"
            ) else (
              echo %REPORT_DIR% exists but contains no subfolders.
            )
          )
        '''
      }
    }

    stage('Archive Reports') {
      steps {
        archiveArtifacts artifacts: 'dd_reports/**/*.pdf, dd_reports/**/*.csv, dd_reports/**/*.txt', allowEmptyArchive: true, onlyIfSuccessful: false
        archiveArtifacts artifacts: 'test-automation-demo/dd_reports/**/*.pdf, test-automation-demo/dd_reports/**/*.csv, test-automation-demo/dd_reports/**/*.txt', allowEmptyArchive: true, onlyIfSuccessful: false
      }
    }
  }

  post {
    always {
      echo "Pipeline finished with status: ${currentBuild.currentResult}"
      bat '''
        if exist app_pid.txt (
          set /p APPPID=<app_pid.txt
          echo Stopping app PID %APPPID%
          powershell -NoProfile -ExecutionPolicy Bypass "Try { Stop-Process -Id %APPPID% -Force -ErrorAction SilentlyContinue } Catch { }"
        )
      '''
    }
    failure {
      echo 'Build FAILED (infra/script error). Reports (if any) are archived above.'
    }
    unstable {
      echo 'Tests reported failures. Build marked UNSTABLE; reports archived.'
    }
    success {
      echo 'All tests passed. Reports archived.'
    }
  }
}
