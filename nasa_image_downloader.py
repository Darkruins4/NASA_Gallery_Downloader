import os
import time
import random
import hashlib
import requests
import logging
from logging.handlers import RotatingFileHandler
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
from PIL import Image
import argparse
import sys

# ---- Basic settings and constants ----
BASE_URL = "https://www.nasa.gov/multimedia/imagegallery/index.html"
MIN_IMAGE_SIZE = 100  # px
MAX_LOAD_ATTEMPTS = 10  # "Load More" button click attempts

IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".bmp"]
FAILED_DOWNLOADS_FILE = "failed_downloads.txt"
LOG_FILE = "downloaded_images.txt"
SCRAPER_LOG_FILE = "scraper_log.txt"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
]

# ---- Argument parsing ----
def parse_args():
    parser = argparse.ArgumentParser(description="NASA Gallery Image Downloader")
    parser.add_argument("-d", "--dir", default=os.path.join("D:", "HDD", "NASA_images"), help="Download directory")
    parser.add_argument("-w", "--workers", type=int, default=3, help="Number of parallel downloads")
    parser.add_argument("-r", "--retries", type=int, default=3, help="Number of retries per image")
    parser.add_argument("--retry-failed", action="store_true", help="Retry only failed downloads (from failed_downloads.txt)")
    parser.add_argument("--min-size", type=int, default=MIN_IMAGE_SIZE, help="Minimum image size (px)")
    return parser.parse_args()

# ---- Logging setup ----
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

# ---- Utility functions ----
def check_directory_writable(directory, logger):
    try:
        os.makedirs(directory, exist_ok=True)
        test_file = os.path.join(directory, ".write_test")
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        return True
    except Exception as e:
        logger.error(f"The target directory is not writable or could not be created: {e}")
        return False

def random_wait(min_sec=1, max_sec=3):
    time.sleep(random.uniform(min_sec, max_sec))

def get_random_user_agent():
    return {"User-Agent": random.choice(USER_AGENTS)}

def create_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-extensions")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

def generate_unique_filename(img_url):
    img_hash = hashlib.md5(img_url.encode()).hexdigest()[:8]
    base = os.path.basename(img_url.split("?")[0])
    base_name, ext = os.path.splitext(base)
    if not ext or ext.lower() not in IMAGE_EXTENSIONS:
        ext = ".jpg"
    return f"{base_name}_{img_hash}{ext}"

def is_valid_image(file_path, min_size, logger):
    try:
        with Image.open(file_path) as img:
            img.verify()
        with Image.open(file_path) as img:
            width, height = img.size
            if width < min_size or height < min_size:
                logger.warning(f"Image too small: {file_path} ({width}x{height})")
                return False
        return True
    except Exception as e:
        logger.warning(f"Invalid image: {file_path} - {e}")
        return False

# ---- Web scraping functions ----
def get_category_links(logger):
    driver = None
    category_links = []
    try:
        driver = create_driver()
        logger.info(f"Fetching category links: {BASE_URL}")
        driver.get(BASE_URL)
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        random_wait(2, 4)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        selectors = [
            [a['href'] for a in soup.find_all('a', href=True) if '/image-feature/' in a['href']],
            [a['href'] for a in soup.find_all('a', href=True) if 'gallery' in a['href']],
            [a['href'] for a in soup.find_all('a', href=True) if 'images' in a['href']]
        ]
        for selector_results in selectors:
            if selector_results:
                category_links = [urljoin(BASE_URL, link) for link in selector_results]
                break
        category_links = list(set(category_links))
        logger.info(f"{len(category_links)} categories found.")
    except TimeoutException as e:
        logger.error(f"Timeout while fetching category links: {e}")
    except Exception as e:
        logger.error(f"Error occurred while fetching category links: {e}")
    finally:
        if driver:
            driver.quit()
    return category_links

def extract_image_url(image_page_url, logger):
    try:
        response = requests.get(image_page_url, headers=get_random_user_agent(), timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        image_url = None
        for property_value in ["og:image", "twitter:image"]:
            meta_tag = soup.find("meta", property=property_value) or soup.find("meta", attrs={"name": property_value})
            if meta_tag and meta_tag.get("content"):
                image_url = meta_tag["content"]
                break
        if not image_url:
            for img in soup.find_all("img", src=True):
                src = img["src"]
                if any(term in src.lower() for term in ["full", "large", "orig", "high-res", "hires"]):
                    image_url = urljoin(image_page_url, src)
                    break
        if not image_url:
            img_tag = soup.find("img", src=True)
            if img_tag:
                image_url = urljoin(image_page_url, img_tag["src"])
        if not image_url:
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                if any(ext in href.lower() for ext in IMAGE_EXTENSIONS):
                    image_url = urljoin(image_page_url, href)
                    break
        return image_url
    except requests.RequestException as e:
        logger.error(f"Error extracting image URL ({image_page_url}): {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error extracting image URL ({image_page_url}): {e}")
        return None

def load_all_images(category_url, logger):
    driver = None
    image_links = []
    try:
        driver = create_driver()
        logger.info(f"Loading images from category: {category_url}")
        driver.get(category_url)
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        random_wait(3, 5)
        load_more_selectors = [
            '//button[contains(text(), "Load")]',
            '//button[contains(text(), "More")]',
            '//a[contains(text(), "Load")]',
            '//a[contains(@class, "load-more")]',
            '//button[contains(@class, "load-more")]'
        ]
        load_attempts = 0
        while load_attempts < MAX_LOAD_ATTEMPTS:
            try:
                clicked = False
                for selector in load_more_selectors:
                    try:
                        load_more_button = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        driver.execute_script("arguments[0].scrollIntoView();", load_more_button)
                        random_wait(1, 2)
                        driver.execute_script("arguments[0].click();", load_more_button)
                        clicked = True
                        logger.info("Loading more images...")
                        random_wait(3, 6)
                        break
                    except TimeoutException:
                        continue
                if not clicked:
                    logger.info("No more images to load.")
                    break
                load_attempts += 1
            except Exception as e:
                logger.error(f"Error occurred while loading more images: {e}")
                break
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        image_selectors = [
            [a["href"] for a in soup.find_all("a", href=True) if "/image-feature/" in a["href"]],
            [a["href"] for a in soup.find_all("a", href=True) if any(ext in a["href"].lower() for ext in IMAGE_EXTENSIONS)],
            [img["src"] for img in soup.find_all("img", src=True) if img["src"].startswith("http")]
        ]
        for selector_results in image_selectors:
            if selector_results:
                image_links = [urljoin(category_url, link) for link in selector_results]
                image_links = list(set(image_links))
                break
        logger.info(f"{len(image_links)} images found in this category.")
    except Exception as e:
        logger.error(f"Error occurred while loading images from category: {e}")
    finally:
        if driver:
            driver.quit()
    return image_links

# ---- Download and processing ----
def download_image(img_url, download_dir, log_file, failed_file, min_img_size, max_retries, logger):
    if not img_url:
        logger.warning("Missing image URL, skipping.")
        return False
    if not any(ext in img_url.lower() for ext in IMAGE_EXTENSIONS):
        actual_img_url = extract_image_url(img_url, logger)
        if not actual_img_url:
            logger.warning(f"Could not extract image URL: {img_url}")
            with open(failed_file, "a", encoding="utf-8") as failed_log:
                failed_log.write(f"{img_url}\n")
            return False
    else:
        actual_img_url = img_url
    img_name = os.path.join(download_dir, generate_unique_filename(actual_img_url))
    if os.path.exists(img_name) and is_valid_image(img_name, min_img_size, logger):
        logger.info(f"Already exists: {img_name}")
        return True
    for attempt in range(max_retries):
        try:
            random_wait(1, 3)
            response = requests.get(
                actual_img_url, 
                stream=True, 
                timeout=20, 
                headers=get_random_user_agent()
            )
            response.raise_for_status()
            content_type = response.headers.get('Content-Type', '')
            if not content_type.startswith('image/'):
                logger.warning(f"Not an image content: {actual_img_url} (Content-Type: {content_type})")
                continue
            with open(img_name, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
            if is_valid_image(img_name, min_img_size, logger):
                logger.info(f"Downloaded successfully: {img_name}")
                with open(log_file, "a", encoding="utf-8") as log_f:
                    log_f.write(f"{actual_img_url}\n")
                return True
            else:
                logger.warning(f"Corrupted file ({img_name}), retrying... ({attempt+1}/{max_retries})")
                if os.path.exists(img_name):
                    os.remove(img_name)
        except requests.RequestException as e:
            logger.error(f"Error occurred during download ({attempt+1}/{max_retries}): {actual_img_url} - {e}")
            random_wait(3, 7)
        except Exception as e:
            logger.error(f"Unexpected error during download ({attempt+1}/{max_retries}): {actual_img_url} - {e}")
            random_wait(3, 7)
    logger.warning(f"Failed to download after {max_retries} attempts: {actual_img_url}")
    with open(failed_file, "a", encoding="utf-8") as failed_log:
        failed_log.write(f"{actual_img_url}\n")
    return False

def process_category(category_link, args, logger):
    logger.info(f"Processing category: {category_link}")
    image_links = load_all_images(category_link, logger)
    if not image_links:
        logger.warning(f"No images found in this category: {category_link}")
        return 0, 0
    success, fail = 0, 0
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_url = {
            executor.submit(
                download_image, url, args.dir, os.path.join(args.dir, LOG_FILE), 
                os.path.join(args.dir, FAILED_DOWNLOADS_FILE), args.min_size, args.retries, logger
            ): url for url in image_links
        }
        for future in as_completed(future_to_url):
            try:
                result = future.result()
                if result:
                    success += 1
                else:
                    fail += 1
            except Exception as e:
                logger.error(f"Thread exception: {e}")
                fail += 1
    logger.info(f"Category summary – successful: {success}, failed: {fail}")
    return success, fail

def retry_failed_images(args, logger):
    failed_file = os.path.join(args.dir, FAILED_DOWNLOADS_FILE)
    if not os.path.exists(failed_file):
        logger.info("No failed_downloads.txt found, nothing to retry.")
        return
    with open(failed_file, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]
    if not urls:
        logger.info("No images to retry in failed_downloads.txt.")
        return
    logger.info(f"Retrying {len(urls)} failed images...")
    new_success, still_failed = 0, 0
    temp_failed = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(
                download_image, url, args.dir, os.path.join(args.dir, LOG_FILE), 
                failed_file, args.min_size, args.retries, logger
            ) for url in urls
        ]
        for i, future in enumerate(as_completed(futures)):
            try:
                if future.result():
                    new_success += 1
                else:
                    temp_failed.append(urls[i])
                    still_failed += 1
            except Exception as e:
                logger.error(f"Thread exception: {e}")
                temp_failed.append(urls[i])
                still_failed += 1
    with open(failed_file, "w", encoding="utf-8") as f:
        for url in temp_failed:
            f.write(url + "\n")
    logger.info(f"Retried downloads - successful: {new_success}, still failed: {still_failed}")

# ---- Main program ----
def main():
    args = parse_args()
    logger = setup_logging(args.dir)

    logger.info("=== NASA Gallery image download started ===")
    logger.info(f"Download directory: {args.dir}")
    logger.info(f"Parallel threads: {args.workers}")
    logger.info(f"Retry attempts: {args.retries}")
    logger.info(f"Minimum image size: {args.min_size}px")

    if not check_directory_writable(args.dir, logger):
        logger.error("The program will exit, as the target directory is not writable.")
        return
    
    open(os.path.join(args.dir, FAILED_DOWNLOADS_FILE), "a", encoding="utf-8").close()
    open(os.path.join(args.dir, LOG_FILE), "a", encoding="utf-8").close()

    try:
        if args.retry_failed:
            retry_failed_images(args, logger)
            return

        category_links = get_category_links(logger)
        if not category_links:
            logger.error("No category links found. Please check the website structure.")
            return

        total_success, total_fail = 0, 0
        for i, category_link in enumerate(category_links):
            logger.info(f"Processing category ({i+1}/{len(category_links)}): {category_link}")
            success, fail = process_category(category_link, args, logger)
            total_success += success
            total_fail += fail
            if i < len(category_links) - 1:
                wait_time = random.uniform(10, 20)
                logger.info(f"Waiting {wait_time:.2f} seconds before next category...")
                time.sleep(wait_time)
        logger.info(f"=== All categories processed! Successful downloads: {total_success}, failed: {total_fail} ===")
    except KeyboardInterrupt:
        logger.info("Program interrupted by user.")
    except Exception as e:
        logger.critical(f"Critical error occurred: {e}")

if __name__ == "__main__":
    main()