from datetime import datetime, timezone
from timezonefinder import TimezoneFinder
import pytz
# from tzfpy import get_tz


class SporeTools:

    tf = TimezoneFinder()

    @staticmethod
    def cast_key(value, target_type):
        if target_type in ['int', 'integer']:
            return int(value)
        if target_type in ['float', 'numeric']:
            return float(value)
        if target_type in ['str', 'string']:
            return str(value)

    @classmethod
    def get_timezone(cls, lat: float, lng: float) -> pytz.timezone:
        # Get timezone name from coordinates
        # return get_tz(lng, lat)  # Note: lon, lat order!
        return cls.tf.timezone_at(lat=lat, lng=lng)

    @classmethod
    def get_utc_datetime(cls, date_str: str, time_str: str, lat: float, lng: float) -> datetime:
        """
        Converts a local match datetime (based on coordinates) to UTC datetime,
        considering DST and timezone of the location.

        :param lat: Latitude of the padel club
        :param lng: Longitude of the padel club
        :param date_str: Date of the match (e.g., "2025-04-30")
        :param time_str: Start time of the match (e.g., "13:00")
        :return: UTC datetime object
        """
        # Step 1: Find the timezone name from coordinates
        timezone_str = cls.tf.timezone_at(lat=lat, lng=lng)
        if not timezone_str:
            raise ValueError("Could not determine timezone from coordinates.")

        # Step 2: Create a naive datetime from date and time
        local_naive = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")

        # Step 3: Localize it using the detected timezone
        local_tz = pytz.timezone(timezone_str)
        local_aware = local_tz.localize(local_naive)

        # Step 4: Convert to UTC
        utc_dt = local_aware.astimezone(pytz.utc)

        return utc_dt

    @classmethod
    def get_local_datetime(cls, utc_dt: datetime, lat: float, lng: float) -> datetime:
        """
        Converts a UTC datetime to the local time based on geographic coordinates,
        considering DST and the actual timezone of the location.

        :param utc_dt: UTC datetime object (must be timezone-aware)
        :param lat: Latitude of the padel club
        :param lng: Longitude of the padel club
        :return: Localized datetime object (with tzinfo)
        """
        # Ensure the UTC datetime is timezone-aware
        if utc_dt.tzinfo is None:
            raise ValueError("UTC datetime must be timezone-aware.")

        # Step 1: Get the timezone string from coordinates
        timezone_str = cls.tf.timezone_at(lat=lat, lng=lng)
        if not timezone_str:
            raise ValueError("Could not determine timezone from coordinates.")

        # Step 2: Convert the UTC datetime to the local timezone
        local_tz = pytz.timezone(timezone_str)
        local_dt = utc_dt.astimezone(local_tz)

        return local_dt

    @staticmethod
    def convert_to_local_time(utc_datetime: datetime, timezone_name: str) -> str:
        """
        Convert UTC datetime to local time string.

        :param utc_datetime: UTC datetime object
        :param timezone_name: IANA timezone name (e.g., "Europe/Paris")
        :return: Formatted local time string in "%Y-%m-%d %H:%M" format
        """
        local_tz = pytz.timezone(timezone_name)
        local_datetime = utc_datetime.astimezone(local_tz)
        return local_datetime.strftime("%Y-%m-%d %H:%M")


if __name__ == '__main__':

    # (lat, lng) = 19.505932556502675, -99.2243537309495    # MEX
    # (lat, lng) = 41.40481597864125, 2.1633451692648578    # BCN
    (lat, lng) = 21.042810960361482, -86.87436061710528   # CUN airport
    # (lat, lng) = 32.84066277149612, -96.9950129035363     # Irving, TX

    timezone_name = SporeTools.get_timezone(lat=lat, lng=lng)
    print(timezone_name)

    local_time = SporeTools.get_local_datetime(utc_dt=datetime.now(timezone.utc), lat=lat, lng=lng)
    print(local_time)