from dataclasses import dataclass
from typing import Optional


@dataclass
class Place:
    name: str = ""
    address: str = ""
    website: str = ""
    phone_number: str = ""
    reviews_count: Optional[int] = None
    reviews_average: Optional[float] = None
    store_shopping: str = "No"
    in_store_pickup: str = "No"
    store_delivery: str = "No"
    place_type: str = ""
    opens_at: str = ""
    introduction: str = ""
    monday: str = ""
    tuesday: str = ""
    wednesday: str = ""
    thursday: str = ""
    friday: str = ""
    saturday: str = ""
    sunday: str = ""
    google_maps_url: str = ""
    latitude: str = ""
    longitude: str = ""
    email: str = ""
    plus_code: str = ""
    price_range: str = ""
    description: str = ""


@dataclass
class Review:
    review_id: str = ""
    author_name: str = ""
    author_url: str = ""
    rating: float = 0.0
    date: str = ""
    text: str = ""
    local_guide: str = ""
    likes: int = 0
