import os
import sys
import subprocess
import threading
import hashlib
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from logging.handlers import RotatingFileHandler
import argparse
from PIL import Image

# --- AUTOMATIC DEPENDENCY MANAGEMENT ---
try:
    import requests
except ImportError:
    print("Required 'requests' module is missing. Installing it automatically...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

try:
    from PIL import Image
except ImportError:
    print("Required 'pillow' module is missing. Installing it automatically...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow"])
    from PIL import Image

# --- GLOBAL CONSTANTS ---
FAILED_DOWNLOADS_FILE = "failed_downloads.txt"
LOG_FILE = "downloaded_images.txt"
SCRAPER_LOG_FILE = "scraper_log.txt"
IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".bmp"]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0"
]

# --- ARGUMENT PARSING ---
def parse_args():
    parser = argparse.ArgumentParser(description="Modern Multithreaded NASA Gallery Image Downloader via Official API")
    parser.add_argument("-q", "--query", type=str, default="nebula", help="Search keyword for NASA assets (e.g., mars, apollo, saturn)")
    parser.add_argument("-d", "--dir", default=os.path.join("D:", "HDD", "NASA_images"), help="Target download directory path")
    parser.add_argument("-w", "--workers", type=int, default=3, help="Number of parallel concurrent download threads")
    parser.add_argument("-r", "--retries", type=int, default=3, help="Maximum number of retries per image download attempt")
    parser.add_argument("--retry-failed", action="store_true", help="Only retry assets listed in failed_downloads.txt")
    parser.add_argument("--min-size", type=int, default=100, help="Minimum acceptable image width/height dimension in pixels")
    return parser.parse_args()

# --- LOGGING SETUP ---
def setup_logging(log_dir):
    logger = logging.getLogger("nasa_scraper")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)
    
    file_handler = RotatingFileHandler(os.path.join(log_dir, SCRAPER_LOG_FILE), maxBytes=2*1024*1024, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)
    return logger

# --- OPERATIONAL VALIDATION ---
def check_directory_writable(directory, logger):
    try:
        os.makedirs(directory, exist_ok=True)
        test_file = os.path.join(directory, ".write_test")
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        return True
    except Exception as e:
        logger.error(f"Target directory is not writable or cannot be created: {e}")
        return False

class ModernNASADownloader:
    def __init__(self, args, logger):
        self.args = args
        self.logger = logger
        self.api_url = "https://githubusercontent.com"
        self.lock = threading.Lock()
        self.failed_file_path = os.path.join(self.args.dir, FAILED_DOWNLOADS_FILE)
        self.success_file_path = os.path.join(self.args.dir, LOG_FILE)

    def _get_headers(self):
        return {"User-Agent": random.choice(USER_AGENTS), "Accept": "application/json"}

    def _save_status(self, filepath, url):
        """Thread-safe analytical logging engine."""
        with self.lock:
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(f"{url}\n")

    def _generate_unique_filename(self, img_url):
        img_hash = hashlib.md5(img_url.encode()).hexdigest()[:8]
        base = os.path.basename(img_url.split("?")[0])
        base_name, ext = os.path.splitext(base)
        if not ext or ext.lower() not in IMAGE_EXTENSIONS:
            ext = ".jpg"
        return f"{base_name}_{img_hash}{ext}"

    def _is_valid_image(self, file_path):
        try:
            with Image.open(file_path) as img:
                img.verify()
            with Image.open(file_path) as img:
                width, height = img.size
                if width < self.args.min_size or height < self.args.min_size:
                    self.logger.warning(f"Skipped (Dimensions below threshold): {file_path} ({width}x{height}px)")
                    return False
            return True
        except Exception as e:
            self.logger.warning(f"Corrupted validation structure: {file_path} - {e}")
            return False

    def fetch_api_clusters(self):
        """Discovers asset structural targets directly via API lookup pipelines."""
        self.logger.info(f"Querying central API registry for keyword: '{self.args.query}'...")
        params = {}
        
        try:
            response = requests.get(self.api_url, params=params, headers=self._get_headers(), timeout=15)
            response.raise_for_status()
            print(f"DEBUG - Status Code: {response.status_code} | First 200 chars of response: {response.text[:200]}")
            data = response.json()
            
            urls = []
            items = data.get("collection", {}).get("items", [])
            for item in items:
                href = item.get("href")
                if href:
                    urls.append(href)
            
            self.logger.info(f"Data discovery phase completed. Found {len(urls)} target items.")
            return urls
        except Exception as e:
            self.logger.error(f"Remote server lookup failed: {e}")
            return []

    def download_image_from_cluster(self, asset_json_url):
        """Processes an asset cluster and downloads the highest resolution file available."""
        retries = 0
        while retries < self.args.retries:
            try:
                time.sleep(random.uniform(0.5, 1.5)) # Politeness delay
                res = requests.get(asset_json_url, headers=self._get_headers(), timeout=10)
                res.raise_for_status()
                image_links = res.json()
                
                # Filter to locate the absolute best resolution available (~orig)
                best_image_url = next((link for link in image_links if "~orig" in link or "orig" in link), image_links[0])
                
                filename = self._generate_unique_filename(best_image_url)
                filepath = os.path.join(self.args.dir, filename)
                
                # Check for existing valid files to avoid duplicate processing overhead
                if os.path.exists(filepath) and self._is_valid_image(filepath):
                    self.logger.info(f"File already verified on local disk: {filename}")
                    return True

                img_res = requests.get(best_image_url, stream=True, headers=self._get_headers(), timeout=20)
                img_res.raise_for_status()
                
                content_type = img_res.headers.get('Content-Type', '')
                if 'image' not in content_type.lower():
                    self.logger.warning(f"Invalid payload format rejected: {content_type}")
                    continue

                with open(filepath, "wb") as f:
                    for chunk in img_res.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                if self._is_valid_image(filepath):
                    self.logger.info(f"Successfully downloaded asset: {filename}")
                    self._save_status(self.success_file_path, best_image_url)
                    return True
                else:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    raise ValueError("File failed integrity validation routines.")
                    
            except Exception as e:
                retries += 1
                self.logger.warning(f"Transient fault at target {asset_json_url}. Retry {retries}/{self.args.retries}. Error: {e}")
                time.sleep(random.uniform(2, 4))
        
        self.logger.error(f"Max retries exhausted. Abandoning target cluster: {asset_json_url}")
        self._save_status(self.failed_file_path, asset_json_url)
        return False

    def retry_failed_pipeline(self):
        """Processes failed downloads directly from error tracking registries."""
        if not os.path.exists(self.failed_file_path) or os.path.getsize(self.failed_file_path) == 0:
            self.logger.info("No failure metrics logged. Skipping error recovery mode.")
            return
            
        with open(self.failed_file_path, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip()]
            
        # Flush file to prevent duplicates during re-processing cycles
        open(self.failed_file_path, "w").close()
        self.logger.info(f"Re-queueing {len(urls)} dropped operational targets...")
        
        success_count, fail_count = 0, 0
        with ThreadPoolExecutor(max_workers=self.args.workers) as executor:
            futures = {executor.submit(self.download_image_from_cluster, url): url for url in urls}
            for future in as_completed(futures):
                if future.result():
                    success_count += 1
                else:
                    fail_count += 1
                    
        self.logger.info(f"Recovery sequence complete. Restored: {success_count}, Remaining failures: {fail_count}")

    def run(self):
        """Core orchestrator driving the download application lifespan."""
        if self.args.retry_failed:
            self.retry_failed_pipeline()
            return

        urls = self.fetch_api_clusters()
        if not urls:
            self.logger.warning("No executable work identified. System lifecycle ending.")
            return

        self.logger.info(f"Spawning thread pool network using {self.args.workers} background pipelines...")
        success_count, fail_count = 0, 0
        
        with ThreadPoolExecutor(max_workers=self.args.workers) as executor:
            futures = {executor.submit(self.download_image_from_cluster, url): url for url in urls}
            for future in as_completed(futures):
                try:
                    if future.result():
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception as e:
                    self.logger.error(f"Fatal worker thread disruption encountered: {e}")
                    fail_count += 1
                    
        self.logger.info(f"=== Execution Summary: Success = {success_count} | Failures = {fail_count} ===")
        
def main():
    args = parse_args()
    os.makedirs(args.dir, exist_ok=True)
    logger = setup_logging(args.dir)

    logger.info("=== NASA Gallery Multithreaded Processing Engine Activated ===")
    logger.info(f"Target Working Storage: {args.dir}")
    logger.info(f"Active Worker Pipelines: {args.workers}")
    logger.info(f"Fault Tolerance Limit: {args.retries}")
    logger.info(f"Dimensional Restriction: {args.min_size}px")

    if not check_directory_writable(args.dir, logger):
        logger.error("Target execution directory cannot be configured. System aborting.")
        return

    # Touch initialization state logs safely
    open(os.path.join(args.dir, FAILED_DOWNLOADS_FILE), "a", encoding="utf-8").close()
    open(os.path.join(args.dir, LOG_FILE), "a", encoding="utf-8").close()

    try:
        downloader = ModernNASADownloader(args, logger)
        downloader.run()
    except KeyboardInterrupt:
        logger.info("Execution sequence manually terminated by operator command.")
    except Exception as e:
        logger.critical(f"System architecture suffered unhandled execution failure: {e}")


if __name__ == "__main__":
    main()
