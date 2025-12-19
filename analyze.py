"""
Swarm Wrapped - Analysis Module

Processes raw Foursquare check-in data and generates statistics for the wrapped report.
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta
import math

# Personality types based on check-in patterns
PERSONALITY_TYPES = {
    "coffee_connoisseur": {
        "name": "The Coffee Connoisseur",
        "emoji": "☕",
        "description": "Your year was fueled by caffeine. Coffee shops were your go-to destination.",
        "categories": ["Coffee Shop", "Café", "Tea Room", "Bakery"],
        "min_percentage": 0.15
    },
    "globe_trotter": {
        "name": "The Globe Trotter",
        "emoji": "🌍",
        "description": "You're a true explorer. Multiple countries and countless cities on your map.",
        "threshold": {"countries": 3, "cities": 30}
    },
    "foodie": {
        "name": "The Foodie",
        "emoji": "🍽️",
        "description": "Life's too short for bad food. Restaurants dominated your check-ins.",
        "categories": ["Restaurant", "Food", "Diner", "Bistro", "Eatery"],
        "min_percentage": 0.20
    },
    "night_owl": {
        "name": "The Night Owl",
        "emoji": "🦉",
        "description": "The night is young! Most of your adventures happened after dark.",
        "time": "night"
    },
    "early_bird": {
        "name": "The Early Bird",
        "emoji": "🌅",
        "description": "Rise and shine! You make the most of mornings.",
        "time": "morning"
    },
    "fitness_fanatic": {
        "name": "The Fitness Fanatic",
        "emoji": "💪",
        "description": "No excuses! Gyms and outdoor activities kept you moving.",
        "categories": ["Gym", "Fitness", "Yoga", "Park", "Trail", "Pool"],
        "min_percentage": 0.15
    },
    "social_butterfly": {
        "name": "The Social Butterfly",
        "emoji": "🦋",
        "description": "Never alone! Most of your check-ins were with friends and family.",
        "threshold": {"friend_percentage": 60}
    },
    "adventurer": {
        "name": "The Adventurer",
        "emoji": "🧭",
        "description": "Variety is the spice of life. You rarely visit the same place twice.",
        "threshold": {"unique_ratio": 0.7}
    },
    "the_regular": {
        "name": "The Regular",
        "emoji": "🪑",
        "description": "You've got your spots. The staff knows your order and your name.",
        "threshold": {"low_unique_ratio": 0.35}
    },
    "homebody": {
        "name": "The Homebody",
        "emoji": "🏠",
        "description": "Home is where the heart is. You know your neighborhood inside and out.",
        "threshold": {"home_city_percentage": 80}
    },
    "jet_setter": {
        "name": "The Jet Setter",
        "emoji": "✈️",
        "description": "Always on the move! Airports are practically your second home.",
        "categories": ["Airport", "Plane", "Terminal"],
        "min_percentage": 0.10
    }
}


# Categories to exclude when privacy filter is enabled
SENSITIVE_CATEGORIES = [
    "church", "cathedral", "mosque", "synagogue", "temple", "chapel",
    "spiritual center", "religious", "school", "elementary", "middle school",
    "high school", "preschool", "daycare", "nursery", "kindergarten"
]


def ordinal(n: int) -> str:
    """Return ordinal string for a number (1st, 2nd, 3rd, etc.)."""
    if 11 <= (n % 100) <= 13:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f"{n}{suffix}"


def format_date_ordinal(dt: datetime) -> str:
    """Format date as 'January 1st' style."""
    return f"{dt.strftime('%B')} {ordinal(dt.day)}"


def analyze_checkins(checkins: list, exclude_sensitive: bool = False) -> dict:
    """
    Analyze a list of Foursquare check-ins and return statistics.

    Args:
        checkins: List of check-in objects from Foursquare API
        exclude_sensitive: If True, exclude churches and schools for privacy

    Returns:
        Dictionary with all computed statistics
    """
    if not checkins:
        return {}

    # Filter out sensitive venues if requested
    if exclude_sensitive:
        filtered_checkins = []
        for checkin in checkins:
            venue = checkin.get("venue", {})
            venue_name = venue.get("name", "").lower()
            categories = venue.get("categories", [])
            category_names = [cat.get("name", "").lower() for cat in categories]

            # Check if any category matches sensitive categories
            is_sensitive = any(
                any(sensitive in cat_name for sensitive in SENSITIVE_CATEGORIES)
                for cat_name in category_names
            )

            # Also check venue name for sensitive keywords
            if not is_sensitive:
                is_sensitive = any(sensitive in venue_name for sensitive in SENSITIVE_CATEGORIES)

            if not is_sensitive:
                filtered_checkins.append(checkin)

        checkins = filtered_checkins

    stats = {}

    # Basic counts
    stats["total_checkins"] = len(checkins)

    # Unique venues
    venues = {}
    venue_counts = Counter()
    category_counts = Counter()
    city_counts = Counter()
    country_counts = Counter()

    # Time distributions
    hourly = Counter()
    daily = Counter()
    monthly = Counter()

    # Date tracking for streaks
    checkin_dates = set()
    checkins_per_day = Counter()

    # Friends
    friend_counts = Counter()
    checkins_with_friends = 0

    # Shouts and photos
    checkins_with_shouts = 0
    total_photos = 0

    # Location tracking for map
    map_points = defaultdict(list)

    for checkin in checkins:
        venue = checkin.get("venue", {})
        venue_id = venue.get("id", "unknown")
        venue_name = venue.get("name", "Unknown Venue")

        # Count venue visits
        venue_counts[venue_name] += 1

        # Store venue info
        if venue_id not in venues:
            location = venue.get("location", {})
            categories = venue.get("categories", [])
            primary_category = categories[0]["name"] if categories else "Other"

            venues[venue_id] = {
                "name": venue_name,
                "category": primary_category,
                "city": location.get("city", "Unknown"),
                "state": location.get("state", ""),
                "country": location.get("country", "Unknown"),
                "lat": location.get("lat"),
                "lng": location.get("lng")
            }

        venue_info = venues[venue_id]

        # Count categories
        category_counts[venue_info["category"]] += 1

        # Count cities
        city_key = venue_info["city"]
        if venue_info["state"]:
            city_key = f"{venue_info['city']}, {venue_info['state']}"
        elif venue_info["country"] != "United States":
            city_key = f"{venue_info['city']}, {venue_info['country']}"
        city_counts[city_key] += 1

        # Count countries
        country_counts[venue_info["country"]] += 1

        # Time analysis - use each check-in's own timezone offset for local time
        created_at = checkin.get("createdAt", 0)
        checkin_tz_offset = checkin.get("timeZoneOffset", 0)  # Minutes from UTC
        # Convert UTC timestamp to datetime, then apply check-in's local timezone
        dt_utc = datetime.utcfromtimestamp(created_at)
        dt = dt_utc + timedelta(minutes=checkin_tz_offset)

        hourly[dt.hour] += 1
        daily[dt.strftime("%A")] += 1
        monthly[dt.strftime("%b")] += 1

        date_str = dt.strftime("%Y-%m-%d")
        checkin_dates.add(date_str)
        checkins_per_day[date_str] += 1

        # Friends
        with_friends = checkin.get("with", [])
        if with_friends:
            checkins_with_friends += 1
            for friend in with_friends:
                friend_name = f"{friend.get('firstName', '')} {friend.get('lastName', '')}".strip()
                if friend_name:
                    friend_counts[friend_name] += 1

        # Shouts and photos
        if checkin.get("shout"):
            checkins_with_shouts += 1
        total_photos += len(checkin.get("photos", {}).get("items", []))

        # Map points
        if venue_info["lat"] and venue_info["lng"]:
            lat_rounded = round(venue_info["lat"], 4)
            lng_rounded = round(venue_info["lng"], 4)
            map_points[(lat_rounded, lng_rounded)].append(f"{venue_name}(1)")

    # Top venues
    stats["unique_venues"] = len(venues)
    stats["top_venues"] = [
        {
            "name": name,
            "count": count,
            **{k: v for k, v in venues.get(
                next((vid for vid, v in venues.items() if v["name"] == name), {}
            ), {}).items() if k != "name"}
        }
        for name, count in venue_counts.most_common(10)
    ]

    # Fix top_venues to include venue details
    top_venues_fixed = []
    for name, count in venue_counts.most_common(10):
        venue_data = next((v for v in venues.values() if v["name"] == name), {})
        top_venues_fixed.append({
            "name": name,
            "count": count,
            "category": venue_data.get("category", ""),
            "city": venue_data.get("city", ""),
            "state": venue_data.get("state", ""),
            "country": venue_data.get("country", "")
        })
    stats["top_venues"] = top_venues_fixed

    # Top categories
    stats["top_categories"] = [
        {"name": name, "count": count}
        for name, count in category_counts.most_common(10)
    ]
    stats["unique_categories"] = len(category_counts)

    # Top cities
    stats["top_cities"] = [
        {"name": name, "count": count}
        for name, count in city_counts.most_common(10)
    ]
    stats["unique_cities"] = len(city_counts)

    # Countries
    stats["countries"] = [
        {"name": name, "count": count}
        for name, count in country_counts.most_common()
    ]

    # Time distributions
    stats["hourly_distribution"] = {str(h): hourly.get(h, 0) for h in range(24)}
    stats["monthly_distribution"] = {
        month: monthly.get(month, 0)
        for month in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    }

    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    stats["daily_distribution"] = {day: daily.get(day, 0) for day in day_order}

    # Peak times
    stats["peak_hour"] = max(hourly, key=hourly.get) if hourly else 0
    stats["peak_hour_formatted"] = f"{stats['peak_hour']}am" if stats["peak_hour"] < 12 else f"{stats['peak_hour']-12 or 12}pm"
    stats["busiest_day"] = max(daily, key=daily.get) if daily else "Unknown"
    stats["busiest_month"] = max(monthly, key=monthly.get) if monthly else "Unknown"

    # Activity stats
    sorted_dates = sorted(checkin_dates)
    stats["days_active"] = len(checkin_dates)

    if sorted_dates:
        first_date = datetime.strptime(sorted_dates[0], "%Y-%m-%d")
        last_date = datetime.strptime(sorted_dates[-1], "%Y-%m-%d")
        total_days = (last_date - first_date).days + 1
        stats["total_days_2025"] = total_days
        stats["activity_percentage"] = round(len(checkin_dates) / total_days * 100, 1) if total_days > 0 else 0
    else:
        stats["total_days_2025"] = 0
        stats["activity_percentage"] = 0

    stats["avg_checkins_per_active_day"] = round(len(checkins) / len(checkin_dates), 1) if checkin_dates else 0

    # Busiest day
    if checkins_per_day:
        max_day = max(checkins_per_day, key=checkins_per_day.get)
        max_day_dt = datetime.strptime(max_day, "%Y-%m-%d")
        stats["max_checkins_day"] = format_date_ordinal(max_day_dt)  # "April 20th"
        stats["max_checkins_count"] = checkins_per_day[max_day]
    else:
        stats["max_checkins_day"] = ""
        stats["max_checkins_count"] = 0

    # Streak calculation
    stats["longest_streak"] = calculate_longest_streak(sorted_dates)

    # Friends stats
    stats["checkins_with_friends"] = checkins_with_friends
    stats["friend_percentage"] = round(checkins_with_friends / len(checkins) * 100, 1) if checkins else 0
    stats["top_friends"] = [
        {"name": name, "count": count}
        for name, count in friend_counts.most_common(5)
    ]

    # Solo stats
    stats["solo_checkins"] = len(checkins) - checkins_with_friends
    stats["solo_percentage"] = round(stats["solo_checkins"] / len(checkins) * 100, 1) if checkins else 0

    # Shouts and photos
    stats["checkins_with_shouts"] = checkins_with_shouts
    stats["shout_percentage"] = round(checkins_with_shouts / len(checkins) * 100, 1) if checkins else 0
    stats["total_photos"] = total_photos

    # Time personality
    morning = sum(hourly.get(h, 0) for h in range(5, 12))
    afternoon = sum(hourly.get(h, 0) for h in range(12, 17))
    evening = sum(hourly.get(h, 0) for h in range(17, 21))
    night = sum(hourly.get(h, 0) for h in list(range(21, 24)) + list(range(0, 5)))

    stats["time_of_day"] = {
        "morning": morning,
        "afternoon": afternoon,
        "evening": evening,
        "night": night
    }

    max_time = max([("morning", morning), ("afternoon", afternoon), ("evening", evening), ("night", night)], key=lambda x: x[1])
    time_personalities = {
        "morning": "Early Bird",
        "afternoon": "Day Explorer",
        "evening": "Evening Wanderer",
        "night": "Night Owl"
    }
    stats["time_personality"] = time_personalities.get(max_time[0], "Explorer")

    # Weekend vs weekday
    weekend = daily.get("Saturday", 0) + daily.get("Sunday", 0)
    weekday = sum(daily.get(d, 0) for d in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
    total = weekend + weekday
    stats["weekend_percentage"] = round(weekend / total * 100, 1) if total > 0 else 0
    stats["weekday_percentage"] = round(weekday / total * 100, 1) if total > 0 else 0

    # First and last check-in
    if checkins:
        first_checkin = min(checkins, key=lambda x: x.get("createdAt", 0))
        last_checkin = max(checkins, key=lambda x: x.get("createdAt", 0))

        # Use each check-in's own timezone offset
        first_dt_utc = datetime.utcfromtimestamp(first_checkin.get("createdAt", 0))
        last_dt_utc = datetime.utcfromtimestamp(last_checkin.get("createdAt", 0))
        first_dt = first_dt_utc + timedelta(minutes=first_checkin.get("timeZoneOffset", 0))
        last_dt = last_dt_utc + timedelta(minutes=last_checkin.get("timeZoneOffset", 0))

        stats["first_checkin"] = {
            "venue": first_checkin.get("venue", {}).get("name", "Unknown"),
            "date": format_date_ordinal(first_dt),
            "time": first_dt.strftime("%I:%M %p").lstrip("0")
        }
        stats["last_checkin"] = {
            "venue": last_checkin.get("venue", {}).get("name", "Unknown"),
            "date": format_date_ordinal(last_dt),
            "time": last_dt.strftime("%I:%M %p").lstrip("0")
        }

    # Map data (grouped by location)
    stats["map_points"] = [
        {"lat": lat, "lng": lng, "v": ",".join(venues)}
        for (lat, lng), venues in map_points.items()
    ]

    # One-time venues (visited only once)
    one_time_venues = sum(1 for count in venue_counts.values() if count == 1)
    stats["one_time_venues"] = one_time_venues
    stats["one_time_percentage"] = round(one_time_venues / len(venues) * 100, 1) if venues else 0

    # Furthest venue from home city (most common city)
    if city_counts and venues:
        home_city = city_counts.most_common(1)[0][0]
        stats["home_city"] = home_city

        # Find home city coordinates (average of all venues in home city)
        home_venues = [v for v in venues.values() if v.get("city") == home_city.split(",")[0]]
        if home_venues:
            home_lat = sum(v.get("lat", 0) for v in home_venues if v.get("lat")) / len([v for v in home_venues if v.get("lat")])
            home_lng = sum(v.get("lng", 0) for v in home_venues if v.get("lng")) / len([v for v in home_venues if v.get("lng")])

            # Find furthest venue
            max_distance = 0
            furthest_venue = None
            for venue_data in venues.values():
                if venue_data.get("lat") and venue_data.get("lng"):
                    dist = haversine_distance(home_lat, home_lng, venue_data["lat"], venue_data["lng"])
                    if dist > max_distance:
                        max_distance = dist
                        furthest_venue = venue_data

            if furthest_venue:
                stats["furthest_venue"] = {
                    "name": furthest_venue["name"],
                    "city": furthest_venue["city"],
                    "country": furthest_venue["country"],
                    "distance_miles": round(max_distance)
                }

    # International check-ins
    us_checkins = sum(1 for checkin in checkins
                      if checkin.get("venue", {}).get("location", {}).get("country") == "United States")
    international_checkins = len(checkins) - us_checkins
    stats["international_checkins"] = international_checkins
    stats["international_percentage"] = round(international_checkins / len(checkins) * 100, 1) if checkins else 0

    # Day with most unique venues
    unique_venues_per_day = defaultdict(set)
    for checkin in checkins:
        created_at = checkin.get("createdAt", 0)
        checkin_tz = checkin.get("timeZoneOffset", 0)
        dt_utc = datetime.utcfromtimestamp(created_at)
        dt = dt_utc + timedelta(minutes=checkin_tz)
        date_str = dt.strftime("%Y-%m-%d")
        venue_name = checkin.get("venue", {}).get("name", "Unknown")
        unique_venues_per_day[date_str].add(venue_name)

    if unique_venues_per_day:
        max_unique_day = max(unique_venues_per_day.keys(), key=lambda d: len(unique_venues_per_day[d]))
        stats["most_unique_venues_day"] = max_unique_day
        stats["most_unique_venues_count"] = len(unique_venues_per_day[max_unique_day])

    # Longest gap between check-ins
    if len(sorted_dates) > 1:
        max_gap = 0
        gap_start = None
        gap_end = None
        for i in range(1, len(sorted_dates)):
            prev_date = datetime.strptime(sorted_dates[i-1], "%Y-%m-%d")
            curr_date = datetime.strptime(sorted_dates[i], "%Y-%m-%d")
            gap = (curr_date - prev_date).days - 1  # Days without check-ins
            if gap > max_gap:
                max_gap = gap
                gap_start = sorted_dates[i-1]
                gap_end = sorted_dates[i]

        stats["longest_gap_days"] = max_gap
        stats["longest_gap_start"] = gap_start
        stats["longest_gap_end"] = gap_end

    # Determine personality type
    stats["personality"] = determine_personality(stats, category_counts, city_counts)

    # Generate year summary sentence
    stats["year_summary"] = generate_year_summary(stats, category_counts, city_counts)

    return stats


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in miles."""
    R = 3959  # Earth's radius in miles

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c


def determine_personality(stats, category_counts, city_counts):
    """Determine user's check-in personality based on their patterns."""
    scores = {}

    total_checkins = stats.get("total_checkins", 0)
    if total_checkins == 0:
        return PERSONALITY_TYPES["adventurer"]  # Default

    # Calculate unique venue ratio once (used by multiple types)
    unique_ratio = stats.get("unique_venues", 0) / total_checkins if total_checkins else 0

    # Score each personality type
    for type_id, type_info in PERSONALITY_TYPES.items():
        score = 0

        # Category-based scoring (with minimum percentage threshold)
        if "categories" in type_info:
            category_checkins = sum(
                category_counts.get(cat, 0)
                for cat in category_counts.keys()
                if any(keyword.lower() in cat.lower() for keyword in type_info["categories"])
            )
            pct = category_checkins / total_checkins if total_checkins else 0
            min_pct = type_info.get("min_percentage", 0)
            # Only score if meets minimum percentage threshold
            if pct >= min_pct:
                score = pct

        # Threshold-based scoring
        elif "threshold" in type_info:
            threshold = type_info["threshold"]
            if "countries" in threshold:
                # Globe trotter: 3+ countries OR 30+ cities
                if len(stats.get("countries", [])) >= threshold["countries"]:
                    score = 0.8
                if stats.get("unique_cities", 0) >= threshold.get("cities", 0):
                    score = max(score, 0.9)
            elif "friend_percentage" in threshold:
                if stats.get("friend_percentage", 0) >= threshold["friend_percentage"]:
                    score = stats["friend_percentage"] / 100
            elif "unique_ratio" in threshold:
                # Adventurer: high unique ratio (lots of new places)
                if unique_ratio >= threshold["unique_ratio"]:
                    score = unique_ratio
            elif "low_unique_ratio" in threshold:
                # The Regular: low unique ratio (frequents same spots)
                if unique_ratio <= threshold["low_unique_ratio"]:
                    # Score inversely - lower ratio = higher score
                    score = 1 - unique_ratio
            elif "home_city_percentage" in threshold:
                if city_counts:
                    home_count = city_counts.most_common(1)[0][1]
                    home_pct = home_count / total_checkins * 100 if total_checkins else 0
                    if home_pct >= threshold["home_city_percentage"]:
                        score = home_pct / 100

        # Time-based scoring
        elif "time" in type_info:
            time_of_day = stats.get("time_of_day", {})
            target_time = type_info["time"]
            time_checkins = time_of_day.get(target_time, 0)
            total_time = sum(time_of_day.values())
            if total_time > 0 and time_checkins / total_time > 0.35:
                score = time_checkins / total_time

        scores[type_id] = score

    # Get highest scoring personality
    best_type = max(scores.keys(), key=lambda k: scores[k])

    return {
        "type": best_type,
        **PERSONALITY_TYPES[best_type]
    }


def generate_year_summary(stats, category_counts, city_counts):
    """Generate a personalized year-in-a-sentence summary."""

    # Category keyword mappings - map Foursquare categories to simple words
    CATEGORY_KEYWORDS = {
        # Food & Drink
        "coffee": "coffee",
        "café": "coffee",
        "cafe": "coffee",
        "tea": "coffee",
        "restaurant": "good food",
        "food": "good food",
        "diner": "good food",
        "bistro": "good food",
        "eatery": "good food",
        "bakery": "good food",
        "pizza": "good food",
        "burger": "good food",
        "sushi": "good food",
        "taco": "good food",
        "bar": "nights out",
        "pub": "nights out",
        "brewery": "craft beer",
        "winery": "wine",
        "cocktail": "nights out",
        # Activities
        "gym": "fitness",
        "fitness": "fitness",
        "yoga": "wellness",
        "spa": "wellness",
        "park": "the outdoors",
        "trail": "the outdoors",
        "beach": "the outdoors",
        "garden": "the outdoors",
        "hotel": "travel",
        "airport": "travel",
        "train": "travel",
        "shop": "shopping",
        "store": "shopping",
        "mall": "shopping",
        "market": "shopping",
        "grocery": "errands",
        "theater": "entertainment",
        "cinema": "movies",
        "movie": "movies",
        "museum": "culture",
        "gallery": "culture",
        "concert": "live music",
        "music venue": "live music",
        "office": "work",
        "coworking": "work",
    }

    # Categories to skip entirely (too specific or awkward)
    SKIP_CATEGORIES = [
        "spiritual", "church", "religious", "school", "education",
        "bank", "atm", "gas", "parking", "automotive", "medical",
        "doctor", "dentist", "hospital", "pharmacy", "laundry",
        "dry cleaner", "post office", "government"
    ]

    # Build category words from top categories
    cat_words = []
    for cat, _ in category_counts.most_common(6):  # Check more to find good ones
        cat_lower = cat.lower()

        # Skip awkward categories
        if any(skip in cat_lower for skip in SKIP_CATEGORIES):
            continue

        # Find matching keyword
        matched = False
        for keyword, replacement in CATEGORY_KEYWORDS.items():
            if keyword in cat_lower:
                if replacement not in cat_words:  # Avoid duplicates
                    cat_words.append(replacement)
                matched = True
                break

        if len(cat_words) >= 2:  # Only need 2 good category words
            break

    # Build the sentence more naturally
    parts = []

    # Opening with categories
    if cat_words:
        parts.append(f"A year of {' and '.join(cat_words)}")
    else:
        parts.append(f"A year of {stats.get('total_checkins', 0)} check-ins")

    # Location context
    if city_counts:
        home_city = city_counts.most_common(1)[0][0].split(",")[0].strip()
        other_cities = [
            c[0].split(",")[0].strip()
            for c in city_counts.most_common(4)[1:]
            if c[0].split(",")[0].strip() != home_city
        ]

        if other_cities:
            if len(other_cities) == 1:
                parts.append(f"based in {home_city} with adventures in {other_cities[0]}")
            else:
                parts.append(f"based in {home_city} with adventures in {other_cities[0]} and {other_cities[1]}")
        else:
            parts.append(f"exploring {home_city}")

    # Pick ONE highlight (streak OR social, not both)
    streak = stats.get("longest_streak", 0)
    friend_pct = stats.get("friend_percentage", 0)

    if streak >= 30:
        parts.append(f"fueled by a {streak}-day streak")
    elif friend_pct >= 60:
        parts.append("shared with loved ones")
    elif friend_pct <= 25 and stats.get("solo_checkins", 0) > 50:
        parts.append("often flying solo")

    # Join with commas for cleaner flow, period at end
    if len(parts) == 1:
        return parts[0] + "."
    elif len(parts) == 2:
        return f"{parts[0]}, {parts[1]}."
    else:
        return f"{parts[0]}, {parts[1]}, {parts[2]}."


def calculate_longest_streak(sorted_dates: list) -> int:
    """Calculate the longest consecutive day streak."""
    if not sorted_dates:
        return 0

    max_streak = 1
    current_streak = 1

    for i in range(1, len(sorted_dates)):
        prev_date = datetime.strptime(sorted_dates[i-1], "%Y-%m-%d")
        curr_date = datetime.strptime(sorted_dates[i], "%Y-%m-%d")

        if (curr_date - prev_date).days == 1:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 1

    return max_streak
