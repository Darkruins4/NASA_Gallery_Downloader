import subprocess
import sys
import os
import importlib
import urllib.request

REQUIRED_PACKAGES = [
    "requests",
    "beautifulsoup4",
    "selenium",
    "webdriver_manager",
    "pillow"
]

CHROMEDRIVER_URLS = [
    "https://googlechromelabs.github.io/chrome-for-testing/",
]

def install_package(package):
    """Install or upgrade a package."""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", package])
        print(f"Successfully installed/upgraded: {package}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error during installation: {package} - {e}")
        return False

def check_and_install_packages():
    """Check and install/upgrade required Python packages."""
    print("Checking/installing Python packages:")
    for pkg in REQUIRED_PACKAGES:
        try:
            importlib.import_module(pkg if pkg != "beautifulsoup4" else "bs4")
            print(f"{pkg} is already installed. Upgrading...")
        except ImportError:
            print(f"{pkg} is not installed. Installing...")
        install_package(pkg)
    print("Python package check/installation complete.\n")

def check_chromedriver_version():
    """Try to get the installed chromedriver version."""
    try:
        result = subprocess.run(["chromedriver", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Installed chromedriver: {result.stdout.strip()}")
            return result.stdout.strip()
        else:
            print("chromedriver is not available in PATH.")
            return None
    except FileNotFoundError:
        print("chromedriver is not installed or not in PATH.")
        return None

def download_chromedriver_with_webdriver_manager():
    """Download the latest chromedriver using webdriver_manager."""
    print("Downloading chromedriver automatically using webdriver_manager...")
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        s = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=s, options=chrome_options)
        driver.quit()
        print("Chromedriver download and test was successful.")
    except Exception as e:
        print("An error occurred while downloading/testing chromedriver:", e)

def main():
    print("NASA image downloader setup utility starting...\n")
    check_and_install_packages()
    cd_version = check_chromedriver_version()
    if cd_version:
        print("Existing chromedriver found, webdriver_manager will update if necessary.\n")
    else:
        print("No chromedriver found, or not available in PATH.")
        download_chromedriver_with_webdriver_manager()
    print("\nSetup complete! The main script can now be run without issues.")

if __name__ == "__main__":
    main()