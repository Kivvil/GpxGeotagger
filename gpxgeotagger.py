import gpxpy
import gpxpy.gpx
import piexif
import time
import datetime
import argparse;
from datetime import timezone
from bisect import bisect_left

class PhotoFile:
    # exif_data is the dictionary acquired from piexif. file_path is the path to the file.
    def __init__(self, file_path: str, exif_data: gpxpy.gpx.Dict):
        self.file_path: str = file_path
        self.exif: gpxpy.gpx.Dict = exif_data

        time_string = self.exif['Exif'][piexif.ExifIFD.DateTimeOriginal].decode("utf-8") + " " + jpeg_time_zone_offset
        time_struct = datetime.datetime.strptime(time_string, "%Y:%m:%d %H:%M:%S %z")
        self.timestamp: int = int((time_struct - datetime.datetime.fromtimestamp(0).replace(tzinfo=timezone.utc)).total_seconds())

class Point:
    def __init__(self, latitude: float, longitude: float, elevation: float, time: int):
        self.latitude: float = latitude
        self.longitude: float = longitude
        self.elevation: float = elevation 
        self.time: int = time

def take_closest(pointList: list[Point], time: int):
    """
    Assumes pointList is sorted. Returns the index to the closest value to time.

    If two numbers are equally close, return the index to the smallest number.
    """
    pos = bisect_left(pointList, time, key=lambda point: point.time)
    if pos == 0:
        return 0
    if pos == len(pointList):
        return len(pointList) - 1
    before = pointList[pos - 1].time
    after = pointList[pos].time
    if after - time < time - before:
        return pos
    else:
        return pos - 1

def decdeg2dms(dd: float) -> tuple[float, float, float]:
    mult = -1 if dd < 0 else 1
    mnt,sec = divmod(abs(dd)*3600, 60)
    deg,mnt = divmod(mnt, 60)
    return mult*deg, mult*mnt, mult*sec

parser = argparse.ArgumentParser(
        prog="GpxGeoTagger",
        description="Geotag JPEG files by comparing the timestamps to a GPX track")
parser.add_argument("-g", "--gpx", required=True, nargs='+', help="The GPX file(s) to use. Can be a wildcard pattern, eg. *.gpx")
parser.add_argument("-j", "--jpeg", required=True, nargs='+', help="JPEG files to geotag. Can be a wildcard pattern, eg. *.jpg")
parser.add_argument("-t", "--timezone", required=True, help="Timezone the JPEG file exif metadata is in. Eg. +03:00")
parser.add_argument("-th", "--threshold", required=False, help="The time difference between the GPX point and photo timestamp can be no longer than this in seconds. Default 2 minutes (120 seconds).", default=120.0, type=float)
args = parser.parse_args()

gpx_files = args.gpx
jpeg_files = args.jpeg
jpeg_time_zone_offset = args.timezone
time_threshold = args.threshold


# A list of lists which contain the GPX points with unix timestamp
gpx_points: list[Point] = []

for file_path in gpx_files:
    with open(file_path, 'r') as gpx_file:
        gpx = gpxpy.parse(gpx_file)
        points = []
        for gpx_point in gpx.walk(only_points=True):
            gpx_points.append(Point(gpx_point.latitude, gpx_point.longitude, gpx_point.elevation, int(time.mktime(gpx_point.time.timetuple()))))
gpx_points.sort(key=lambda point: point.time)

photos: list[PhotoFile] = []
for file_path in jpeg_files:
    photos.append(PhotoFile(file_path, piexif.load(file_path)))

results: list[tuple[str, bool, float]] = []

# Start searching for gpx points whose timestamps match to those of the photos.
for photo in photos:
    # Take the closest point of the points found in each track
    closest_point_index = take_closest(gpx_points, photo.timestamp)
    closest_point = gpx_points[closest_point_index]
    if abs(closest_point.time - photo.timestamp) > time_threshold:
        results.append((photo.file_path, False, abs(closest_point.time - photo.timestamp)))
        continue

    has_elevation = closest_point.elevation != None
    if closest_point_index == len(gpx_points) - 1 or closest_point_index == 0 or photo.timestamp == closest_point.time:
        latitude = closest_point.latitude
        longitude = closest_point.longitude
        if has_elevation:
            elevation = closest_point.elevation
    elif photo.timestamp > closest_point.time:
        next_point = gpx_points[closest_point_index + 1]
        # Linearly interpolate between closest_point and next_point based on the time passed when the photo was taken
        # A value between 0..1 indicating the progress in time
        progress_between_points = (photo.timestamp - closest_point.time) / (next_point.time - closest_point.time)
        latitude = progress_between_points * (next_point.latitude - closest_point.latitude) + closest_point.latitude
        longitude = progress_between_points * (next_point.longitude - closest_point.longitude) + closest_point.longitude
        if has_elevation:
            elevation = progress_between_points * (next_point.elevation - closest_point.elevation) + closest_point.elevation
    elif closest_point.time > photo.timestamp:
        previous_point = gpx_points[closest_point_index - 1]
        progress_between_points = (photo.timestamp - previous_point.time) / (closest_point.time - previous_point.time)
        latitude = progress_between_points * (closest_point.latitude - previous_point.latitude) + previous_point.latitude
        longitude = progress_between_points * (closest_point.longitude - previous_point.longitude) + previous_point.longitude
        if has_elevation:
            elevation = progress_between_points * (closest_point.elevation - previous_point.elevation) + previous_point.elevation
    else:
        latitude = closest_point.latitude
        longitude = closest_point.longitude
        if has_elevation:
            elevation = closest_point.elevation

    lat_d, lat_m, lat_s = decdeg2dms(abs(latitude))
    lon_d, lon_m, lon_s = decdeg2dms(abs(longitude))

    photo.exif['GPS'][piexif.GPSIFD.GPSVersionID] = [2, 3, 0, 0]
    photo.exif['GPS'][piexif.GPSIFD.GPSLatitudeRef] = b'N' if latitude >= 0.0 else b'S'
    photo.exif['GPS'][piexif.GPSIFD.GPSLongitudeRef] = b'E' if longitude >= 0.0 else b'W'
    photo.exif['GPS'][piexif.GPSIFD.GPSLatitude] = ((int(lat_d * 1000), 1000), (int(lat_m * 1000), 1000), (int(lat_s * 1000), 1000))
    photo.exif['GPS'][piexif.GPSIFD.GPSLongitude] = ((int(lon_d * 1000), 1000), (int(lon_m * 1000), 1000), (int(lon_s * 1000), 1000))

    if has_elevation:
        photo.exif['GPS'][piexif.GPSIFD.GPSAltitudeRef] = 0 if elevation >= 0.0 else 1
        photo.exif['GPS'][piexif.GPSIFD.GPSAltitude] = (int(abs(elevation * 100)), 100)

    piexif.insert(piexif.dump(photo.exif), photo.file_path)
    results.append((photo.file_path, True, abs(closest_point.time - photo.timestamp)))

geotagged_results = list(filter(lambda result : result[1], results))
not_geotagged_results = list(filter(lambda result : result[1] == False, results))

print('--- Geotagged photos (time difference between GPX track point and photo timestamp) --- \n')
for result in geotagged_results:
    print(f'{result[0]}: {result[2]} s.')

if len(not_geotagged_results) > 0:
    print('\n--- Not geotagged photos (time difference between GPX track point and photo timestamp) --- \n')
    for result in not_geotagged_results:
        print(f'{result[0]}: {result[2]} s.')
    print(f"Some photos could not be geotagged because the time difference between the closest GPX track point and the photo timestamp is greater than the threshold ({time_threshold} seconds). You can change the threshold using the --threshold flag. The timezone of the photo files may also be set incorrectly. The time zone can be set using the --timezone flag.\n")



