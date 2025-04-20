# !!This is NOT tested!!

(And please read the "Story" section")

# Story
As you may have already read, this hasn’t been tested, so run it at your own risk. It was 100% made by AI because I don’t understand anything about programming. Now you might ask, “Then why did you make it?” Well, I made it because I was bored during spring break and because there are some cool images there. So yeah, I kind of got bored of the whole thing (though to be honest, I didn’t really have to do much—just copy-pasting stuff here and there), so I’m probably not going to touch the full project again (maybe in 10 years or so). The license is included, so if someone stumbles upon this, understands it, and actually reads all this somehow, feel free to do whatever you want with it (well, not anything, don’t drift too far from the original idea).

# This is made by using: 
- ChatGPT (GPT-4o)
- GitHub Copilot (GPT-4.1)
- Claude (3.7 Sonnet)
- Perplexity (Perplexity Pro)
- Google Cloud Assistant (Preview)

## Recommendation
For a full gallery scrape, have at least 100 GB of free space available.
If you want to be absolutely safe, and especially if you plan to download original TIFFs or all available full-res images, consider 250–500 GB or more.

## NASA Gallery Image Downloader

This Python script automatically downloads images from the NASA gallery, with multithreading, logging, and error handling.

### Usage

1. **Dependency and environment setup:**

Run the setup script (this checks/installs the required Python packages and drivers):

```sh
python setup_nasa_image_downloader.py
```

2. **Start downloading:**

```sh
python nasa_image_downloader.py [-d DOWNLOAD_DIR] [-w NUM_THREADS] [-r RETRIES] [--min-size PIXELS] [--retry-failed]
```

#### Examples

- Use the default download folder:  
  `python nasa_image_downloader.py`
- Use a custom download folder with 5 threads:  
  `python nasa_image_downloader.py -d "C:/temp/nasa" -w 5`
- Retry only the failed downloads:  
  `python nasa_image_downloader.py --retry-failed`

### Main features

- Fully configurable via command-line arguments.
- Rotating logging: max 2MB, 3 old logs.
- Failed downloads can be retried.
- Image size, number of threads, and retries are configurable.
- Fully English code and logging/messages.

### Log files

- `scraper_log.txt`: Log of all events.
- `downloaded_images.txt`: URLs of successfully downloaded images.
- `failed_downloads.txt`: URLs of failed downloads (can be retried).

### License

See LICENSE file.
