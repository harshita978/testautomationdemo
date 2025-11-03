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
    START_URL = ''   // set if you want to override inside CI
    PYTHONDONTWRITEBYTECODE = '1'
    PYTHONUNBUFFERED = '1'
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

          rem Install app deps if present
          if exist oracle_demo\\requirements.txt (
            python -m pip install -r oracle_demo\\requirements.txt
          )

          rem Install browsers (Windows: no --with-deps)
          python -m playwright install
        '''
      }
    }

    // Start the Flask app first (single-line PowerShell to avoid ^ issues)
    stage('Start oracle_demo app') {
      steps {
        bat '''
          if not exist oracle_demo\\app.py (
            echo ERROR: oracle_demo\\app.py not found. Check repo layout.
            exit /b 1
          )

          rem Pick URL: use START_URL if set, else default to http://127.0.0.1:5000
          set "APP_URL=%START_URL%"
          if "%APP_URL%"=="" set "APP_URL=http://127.0.0.1:5000"
          echo Will wait for APP_URL=%APP_URL%

          rem Launch app in background and capture PID
          powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = Start-Process -FilePath 'python' -ArgumentList 'app.py' -WorkingDirectory 'oracle_demo' -PassThru; [IO.File]::WriteAllText('app_pid.txt', $p.Id.ToString()); Write-Host ('App PID: ' + $p.Id)"

          rem Wait until app responds, up to WAIT_TIMEOUT ms
          powershell -NoProfile -ExecutionPolicy Bypass -Command "$deadline=(Get-Date).AddMilliseconds([int]$env:WAIT_TIMEOUT); while((Get-Date) -lt $deadline){ try{ iwr -Uri $env:APP_URL -UseBasicParsing -TimeoutSec 2 ^| Out-Null; exit 0 } catch { Start-Sleep -Milliseconds 300 } }; exit 1"
          if errorlevel 1 (
            echo ERROR: App did not become ready on %APP_URL% within %WAIT_TIMEOUT% ms
            type app_pid.txt
            exit /b 1
          )
          echo App is up at %APP_URL%
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
      // Gracefully stop the app we started
      bat '''
        if exist app_pid.txt (
          for /f "usebackq delims=" %%P in ("app_pid.txt") do set APPPID=%%P
          if not "%APPPID%"=="" (
            echo Stopping app PID %APPPID%
            powershell -NoProfile -ExecutionPolicy Bypass -Command "Try { Stop-Process -Id $env:APPPID -Force -ErrorAction SilentlyContinue } Catch { }"
          )
        )
      '''
    }
  }
}
