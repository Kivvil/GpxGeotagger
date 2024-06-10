# Gpx geotagger

A python script which automatically geotags JPEG photos by comparing their timestamps to the points of a GPX track file.

## How it works
The geotagging works by finding the two closest GPX track points in time to the photo file. The coordinates of the photo are then calculated by linearly interpolating between these points by the time passed between them when the photo was taken. This does not work if the GPX files do not contain time information of the EXIF metadata of the JPEG files do not contain the tag DateTimeOriginal.

## How to use
First download the script and install Python 3 and pip3. Then install the required Python modules:  
```bash
pip3 install gpxpy
pip3 install piexif
pip3 install argparse
```

Now you can put a bunch of GPX files to read and JPEG files to geotag into a directory and run:  
```bash
python3 gpxgeotagger.py -j *.jpg -g *.gpx -t [the timezone of the photo files, eg. +03:00]
```
This will add the GPX exif tags to the JPEG files. A close enough GPX track point in time to the photo may not be found. This will happen if the GPX file was not recorded while the photos were taken or the timestamps are otherwise incorrect. You can adjust the time threshold in seconds using the --threshold command line argument (note that too long a threshold may cause incorrect coordinates). 
