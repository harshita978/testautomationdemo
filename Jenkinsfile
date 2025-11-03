pipeline {
  agent any

  options {
    timeout(time: 30, unit: 'MINUTES')
    timestamps()
    skipDefaultCheckout(true)
  }

  environment {
    // Test & app settings
    WAIT_TIMEOUT = '60000'                 // allow up to 60s for app to boot
    NAV_TIMEOUT  = '7000'
    SCREENSHOT_EVERY_ACTION   = 'false'
    SCREENSHOT_ON_FAILURE     = 'true'
    SCREENSHOT_ON_SUCCESS_END = 'false'
    FULL_PAGE_SHOTS           = 'false'
    START_URL = 'http://127.0.0.1:5000'   // ensure tests and health-check use same URL
    PYTHONDONTWRITEBYTECODE = '1'
    PYTHONUNBUFFERED        = '1'

    // App path (lowercase as you confirmed)
    APP_DIR = 'oracle_demo'
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

    stage('Detect project folder') {
      steps {
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
        bat '''
          for /f "usebackq delims=" %%A in ("run_dir.txt") do set %%A
          echo Using RUN_DIR=%RUN_DIR%
          echo Using APP_DIR=%APP_DIR%

          python -V
          python -m pip install -U pip setuptools wheel

          if exist %RUN_DIR%\\requirements.txt (
            python -m pip install -r %RUN_DIR%\\requirements.txt
          ) else (
            python -m pip install playwright reportlab matplotlib
          )

          rem Install app deps if present
          if exist %APP_DIR%\\requirements.txt (
            python -m pip install -r %APP_DIR%\\requirements.txt
          )

          rem Install browsers (Windows: no --with-deps)
          python -m playwright install
        '''
      }
    }

    // Start the Flask app and keep it alive through tests
    stage('Start oracle_demo app') {
      steps {
        bat '''
          if not exist %APP_DIR%\\app.py (
            echo ERROR: %APP_DIR%\\app.py not found. Check repo layout.
            dir /b %APP_DIR%
            exit /b 1
          )

          rem Free port 5000 if already occupied (previous stale run, etc.)
          for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r ":5000.*LISTENING"') do (
            echo Found listener on 5000 with PID %%P, killing...
            taskkill /PID %%P /F >nul 2>&1
          )

          rem Create a shim so we control host/port and disable reloader
          > serve_app.py (
            echo import sys
            echo sys.path.insert(0, r"%APP_DIR%")
            echo import app as _m
            echo app = getattr(_m, "app", None)
            echo if app is None:
            echo     raise RuntimeError("Expected 'app' Flask instance in %APP_DIR%/app.py")
            echo app.run(host="127.0.0.1", port=5000, use_reloader=False, threaded=True)
          )

          rem Launch in background; capture real PID and logs
          powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = Start-Process -FilePath 'python' -ArgumentList '-u','serve_app.py' -RedirectStandardOutput 'app.out.log' -RedirectStandardError 'app.err.log' -PassThru; [IO.File]::WriteAllText('app_pid.txt', $p.Id.ToString()); Write-Host ('App PID: ' + $p.Id)"

          rem Health check until START_URL responds (up to WAIT_TIMEOUT ms)
          powershell -NoProfile -ExecutionPolicy Bypass -Command "$deadline=(Get-Date).AddMilliseconds([int]$env:WAIT_TIMEOUT); while((Get-Date) -lt $deadline){ try{ iwr -Uri $env:START_URL -UseBasicParsing -TimeoutSec 2 ^| Out-Null; exit 0 } catch { Start-Sleep -Milliseconds 300 } }; exit 1"
          if errorlevel 1 (
            echo ERROR: App did not become ready on %START_URL% within %WAIT_TIMEOUT% ms
            echo ===== app.out.log (tail) =====
            powershell -NoProfile -Command "if (Test-Path 'app.out.log') { Get-Content 'app.out.log' -Tail 200 } else { Write-Host 'no app.out.log' }"
            echo ===== app.err.log (tail) =====
            powershell -NoProfile -Command "if (Test-Path 'app.err.log') { Get-Content 'app.err.log' -Tail 200 } else { Write-Host 'no app.err.log' }"
            for /f "usebackq delims=" %%P in ("app_pid.txt") do set KPID=%%P
            if not "%KPID%"=="" taskkill /PID %KPID% /F >nul 2>&1
            exit /b 1
          )
          echo App is UP at %START_URL%
        '''
      }
    }

    stage('Run tests') {
      steps {
        // If your runner reads START_URL from env, it will pick it up (we set it above)
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
        archiveArtifacts artifacts: 'dd_reports/**', allowEmptyArchive: true, onlyIfSuccessful: false
        archiveArtifacts artifacts: 'test-automation-demo/dd_reports/**', allowEmptyArchive: true, onlyIfSuccessful: false
      }
    }
  }

  post {
    always {
      echo "Pipeline finished with status: ${currentBuild.currentResult}"
      // Cleanly stop the app we started (only after tests & archiving)
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
