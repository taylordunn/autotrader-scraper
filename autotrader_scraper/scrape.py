import csv
import json
import logging
import re
from datetime import datetime
from typing import List, Optional

import bs4
import requests

logging.basicConfig(level=logging.INFO)

URL_BASE = "https://www.autotrader.ca"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36"
}

def search_autotrader(
    make: str, model: str, postal_code: str, radius_km: int = 100, display_results: int = 15,
) -> bs4.BeautifulSoup:
    """
    Searches AutoTrader for cars based on specified parameters.

    This function constructs a URL based on the provided car make, model, 
    postal code, search radius, and number of results to display. It then 
    sends a GET request to AutoTrader and returns the parsed HTML content 
    as a BeautifulSoup object.

    Args:
        make (str): The make of the car (e.g., 'Toyota').
        model (str): The model of the car (e.g., 'Camry').
        postal_code (str): The postal code to search within (e.g., '90210').
        radius_km (int, optional): The search radius in kilometers. Defaults to 100.
        display_results (int, optional): The number of results to display. Defaults to 15. Valid values are 15, 25, 50, 100.

    Returns:
        bs4.BeautifulSoup: Parsed HTML content of the search results page.
    """

    url = (
        URL_BASE
        + "/cars/?"
        + "&".join(
            [f"loc={postal_code}", f"make={make}", f"mdl={model}", f"prx={radius_km}", f"rcp={display_results}"]
        ).replace(" ", "%20")
    )
    logging.info(f"Requesting the search page: {url}")

    r = requests.get(url, timeout=15, headers=HEADERS)
    return bs4.BeautifulSoup(r.content, "html.parser")


def get_car_page_urls(search_page: bs4.BeautifulSoup) -> List[str]:
    """
    Extracts and returns a list of unique car page URLs from a given search page.

    This function scans the provided BeautifulSoup object (`search_page`) for all anchor (`<a>`) tags with specific class attributes, 
    then extracts their `href` attributes to form full URLs. It ensures that the returned list contains only unique URLs.

    Args:
        search_page (bs4.BeautifulSoup): A BeautifulSoup object representing the HTML content of the search page.

    Returns:
        List[str]: A list of unique car page URLs as strings.
    """
    tags = search_page.find_all("a", attrs={"class": ["detail-price-area", "inner-link"]})

    car_page_urls = []
    for _, tag in enumerate(tags):

        car_url = tag.get("href")
        car_url = URL_BASE + str(car_url)
        car_page_urls.append(car_url)

    return list(set(car_page_urls))


def get_car_pages(car_page_urls: List[str]) -> List[bs4.BeautifulSoup]:
    """
    Fetches and returns the HTML content of multiple car pages as BeautifulSoup objects.

    This function takes a list of car page URLs, sends HTTP GET requests to each URL, and parses the returned HTML content into 
    BeautifulSoup objects. The function logs each request and collects the parsed HTML in a list.

    Args:
        car_page_urls (List[str]): A list of URLs for individual car pages to be fetched.

    Returns:
        List[bs4.BeautifulSoup]: A list of BeautifulSoup objects, each representing the parsed HTML content of a car page.
    """
    car_pages = []
    for car_page_url in car_page_urls:
        logging.info(f"Requesting the car page: {car_page_url}")

        r = requests.get(car_page_url, timeout=15, headers=HEADERS)
        car_page = bs4.BeautifulSoup(r.content, "html.parser")
        car_pages.append(car_page)

    return car_pages


def extract_car_data(car_page: bs4.BeautifulSoup) -> dict:
    """
    Extracts car data from a BeautifulSoup object representing a car page.

    This function parses the car page to find a JSON-LD script containing car information,
    and extracts relevant details into a dictionary.

    Args:
        car_page (bs4.BeautifulSoup): A BeautifulSoup object representing the HTML content of a car page.

    Returns:
        dict: A dictionary containing the following car details:
            - url (str): The URL of the car listing.
            - name (str): The name of the car.
            - make (str): The brand/make of the car.
            - model (str): The model of the car.
            - year (str): The manufacturing year of the car.
            - color (str): The color of the car.
            - mileage (int): The mileage of the car.
            - mileage_unit (str): The unit of the mileage.
            - price (float): The price of the car.
            - price_currency (str): The currency of the price.
            - availability (str): The availability status of the car.
            - engine_type (str): The type of engine in the car.
            - fuel_type (str): The type of fuel used by the car.
            - transmission (str): The transmission type of the car.
            - vehicle_configuration (str): The configuration of the vehicle.
    """
    json_data = json.loads(
        car_page.find_all("script", {"type": "application/ld+json"})[1].text
    )
    logging.info(f"Extracting data for: {json_data["name"]}, ({json_data["url"]})")

    return {
        "url": json_data.get("url", None),
        "name": json_data.get("name", None),
        "make": json_data["brand"]["name"],
        "model": json_data.get("model", None),
        "year": json_data.get("vehicleModelDate", None),
        "color": json_data.get("color", None),
        "mileage": json_data.get("mileageFromOdometer", {}).get("value", None),
        "mileage_unit": json_data.get("mileageFromOdometer", {}).get("unitCode", None),
        "price": json_data.get("offers", {}).get("price", None),
        "price_currency": json_data.get("offers", {}).get("priceCurrency", None),
        "availability": json_data.get("offers", {}).get("availability", None),
        "engine_type": json_data.get("vehicleEngine", {}).get("engineType", None),
        "fuel_type": json_data.get("vehicleEngine", {}).get("fuelType", None),
        "transmission": json_data.get("vehicleTransmission", None),
        "vehicle_configuration": json_data.get("vehicleConfiguration", None),
    }


def extract_extra_car_data(car_page: bs4.BeautifulSoup) -> Optional[dict]:
    """
    Extracts additional car data from a BeautifulSoup object representing a car page.

    This function searches the car page for JavaScript containing specific car information,
    extracts the JSON data, and returns it in a structured dictionary.

    Args:
        car_page (bs4.BeautifulSoup): A BeautifulSoup object representing the HTML content of a car page.

    Returns:
        dict: A dictionary containing the following extra car details:
            - highlight_items (list): List of car highlights.
            - feature_highlights (list): List of feature highlights.
            - feature_options (list): List of feature options.
            - trim (str): The trim level of the car.
            - location (str): The location of the car.
            - price_analysis (dict): Price analysis of the car.
            - price_analysis_description (str): Description of the price analysis.
            - vehicle_age (int): The age of the vehicle.
            - stock_number (str): The stock number of the car.
            - dealer_name (str): The name of the dealer.
            - mileage_analysis (str): Analysis of the car's mileage.
            - fuel_economy_city (float): Fuel economy in the city (L/100km).
            - fuel_economy_highway (float): Fuel economy on the highway (L/100km).
            - fuel_economy_combined (float): Combined fuel economy (L/100km).
            - fuel_cost_cents_per_litre (float): Fuel cost in cents per litre.
            - specs (list): List of car specifications.
            - description (list): Description of the car.
            - price_analysis_description (str): Price analysis of the car.
            - price_analysis_market_price (str): Market price of the car.
            - price_analysis_evaluation (str): Price evaluation of the car.
    """
    js_data = car_page.find_all("script", {"type": "text/javascript"})
    js_data = [jd for jd in js_data if "ngVdpModel" in jd.text][0]

    # Use regex to find the JSON object
    json_match = re.search(r"window\[\'ngVdpModel\'\] = ({.*?});", js_data.contents[0])

    if json_match:
        json_str = json_match.group(1)
        json_data = json.loads(json_str)

        return {
            "highlight_items": json_data.get("highlights", {}).get("items", []),
            "feature_highlights": json_data.get("featureHighlights", []),
            "feature_options": json_data.get("featureHighlights", []),
            "trim": json_data.get("hero", {}).get("trim", None),
            "location": json_data.get("hero", {}).get("location", None),
            "vehicle_age": json_data.get("hero", {}).get("vehicleAge", None),
            "stock_number": json_data.get("hero", {}).get("stockNumber", None),
            "dealer_name": json_data.get("ngIcoModel", {}).get("dealerName", None),
            "mileage_analysis": json_data.get("conditionAnalysis", {}).get("odometerCondition", None),
            "fuel_economy_city": json_data.get("fuelEconomy", {}).get("fuelCity", None),
            "fuel_economy_highway": json_data.get("fuelEconomy", {}).get("fuelHighway", None),
            "fuel_economy_combined": json_data.get("fuelEconomy", {}).get("fuelCombined", None),
            "fuel_cost_cents_per_litre": json_data.get("fuelEconomy", {}).get("fuelCost", None),
            "specs": json_data.get("specifications", None),
            "description": json_data["description"].get("description", None),
            "price_analysis": json_data.get("priceAnalysis", {}).get("priceAnalysisDescription", None),
            "price_analysis_market_price": json_data.get("priceAnalysis", {}).get("priceAnalysisMarketPrice", None),
            "price_analysis_evaluation": json_data.get("priceAnalysis", {}).get("priceEvaluation", None),
        }

    return None


if __name__ == "__main__":
    postal_code = "B3M 0L8"
    radius_km = 100
    display_results = 100

    cars = [("Mazda", "CX-5"), ("Toyota", "RAV4"), ("Honda", "CR-V")]


    for car in cars:
        make, model = car
        logging.info(f"Searching for {make} {model}")
        search_page = search_autotrader(make, model, postal_code, radius_km, display_results=display_results)

        car_page_urls = get_car_page_urls(search_page)
        car_pages = get_car_pages(car_page_urls)

        car_data_list = []
        for car_page in car_pages:
            car_data = extract_car_data(car_page)
            extra_car_data = extract_extra_car_data(car_page)
            if extra_car_data:
                car_data.update(extra_car_data)

            car_data_list.append(car_data)


        if len(car_data_list) > 0:
            out_file = f"data/{make.lower()}_{model.lower()}_{datetime.now().strftime("%Y-%m-%d")}.csv"
            with open(out_file, mode="w", newline="") as file:
                logging.info(f"Writing data to file: {out_file}")
                writer = csv.DictWriter(file, fieldnames=car_data_list[0].keys())

                writer.writeheader()
                writer.writerows(car_data_list)

