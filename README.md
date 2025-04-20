# NASA Gallery Image Downloader

This Python script automatically downloads images from the NASA gallery, with multithreading, logging, and error handling.

## Usage

1. **Dependency and environment setup:**

Run the setup script (this checks/installs the required Python packages and drivers):

```sh
python setup_nasa_image_downloader.py
```

2. **Start downloading:**

```sh
python nasa_image_downloader.py [-d DOWNLOAD_DIR] [-w NUM_THREADS] [-r RETRIES] [--min-size PIXELS] [--retry-failed]
```

### Examples

- Use the default download folder:  
  `python nasa_image_downloader.py`
- Use a custom download folder with 5 threads:  
  `python nasa_image_downloader.py -d "C:/temp/nasa" -w 5`
- Retry only the failed downloads:  
  `python nasa_image_downloader.py --retry-failed`

## Main features

- Fully configurable via command-line arguments.
- Rotating logging: max 2MB, 3 old logs.
- Failed downloads can be retried.
- Image size, number of threads, and retries are configurable.
- Fully English code and logging/messages.

## Log files

- `scraper_log.txt`: Log of all events.
- `downloaded_images.txt`: URLs of successfully downloaded images.
- `failed_downloads.txt`: URLs of failed downloads (can be retried).

## License

See LICENSE file.
