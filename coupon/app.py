# from flask import Flask, jsonify, request, render_template
# import folium
# import openrouteservice
# import pandas as pd
# from shapely.geometry import Point, LineString, MultiPolygon, mapping
# from shapely.ops import unary_union

# app = Flask(__name__)
# from flask_cors import CORS
# CORS(app)

# # Load crime dataset
# file_path = "crime_dataset_final_cleaned_processed.csv"
# df = pd.read_csv(file_path)
# df = df[['Latitude', 'Longitude']].dropna()

# API_KEY = "5b3ce3597851110001cf62487728600986d14f3a8c4bce2711134303"  # Replace with your key

# client = openrouteservice.Client(key=API_KEY)

# def get_route(start, dest, avoid_polygons=None):
#     """Get route between two points, avoiding crime zones if specified."""
#     try:
#         params = {
#             "coordinates": [(start[1], start[0]), (dest[1], dest[0])],  # (lon, lat) format
#             "profile": "driving-car",
#             "format": "geojson",
#             "validate": True
#         }
#         if avoid_polygons:
#             params["options"] = {"avoid_polygons": mapping(avoid_polygons)}

#         return client.directions(**params)
#     except Exception as e:
#         return None

# def filter_crimes_along_route(route_coords, buffer_distance=300):
#     """Filter crime hotspots along a given route."""
#     route_line = LineString(route_coords)
#     nearby_crimes = [
#         (row["Latitude"], row["Longitude"])
#         for _, row in df.iterrows()
#         if route_line.distance(Point(row["Longitude"], row["Latitude"])) * 111000 <= buffer_distance
#     ]
#     return nearby_crimes

# def create_crime_zones(crime_hotspots, buffer_size=0.002):
#     """Create high-crime area polygons."""
#     crime_points = [Point(lon, lat) for lat, lon in crime_hotspots]
#     if not crime_points:
#         return None

#     crime_buffers = [p.buffer(buffer_size) for p in crime_points]
#     return unary_union(crime_buffers)  # Merge overlapping zones

# @app.route("/")
# def index():
#     return render_template("index.html")  # Load the frontend

# @app.route("/route", methods=["POST"])
# def get_safe_route():
#     try:
#         data = request.json
#         source = (data["source"]["lat"], data["source"]["lng"])
#         destination = (data["destination"]["lat"], data["destination"]["lng"])

#         # Get primary route
#         primary_route = get_route(source, destination)
#         if not primary_route:
#             return jsonify({"error": "No route found."}), 400

#         # Extract primary route coordinates
#         route_coords = [(coord[0], coord[1]) for coord in primary_route["features"][0]["geometry"]["coordinates"]]

#         # Get crime hotspots
#         crime_hotspots_primary = filter_crimes_along_route(route_coords, buffer_distance=500)
#         crime_zones = create_crime_zones(crime_hotspots_primary)

#         alternative_route = None
#         crime_hotspots_alt = []

#         if crime_zones:
#             alternative_route = get_route(source, destination, avoid_polygons=crime_zones)
#             if alternative_route:
#                 alt_route_coords = [(coord[0], coord[1]) for coord in alternative_route["features"][0]["geometry"]["coordinates"]]
#                 crime_hotspots_alt = filter_crimes_along_route(alt_route_coords, buffer_distance=500)

#         return jsonify({
#             "primary_route": primary_route,
#             "alternative_route": alternative_route,
#             "crime_hotspots_primary": crime_hotspots_primary,
#             "crime_hotspots_alt": crime_hotspots_alt
#         })

#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

# if __name__ == "__main__":
#     app.run(debug=True)






from flask import Flask, request, jsonify
from flask_cors import CORS
import openrouteservice
import pandas as pd
from shapely.geometry import Point, LineString, MultiPolygon, mapping
from shapely.ops import unary_union

# Initialize Flask app and CORS
app = Flask(__name__)
CORS(app)  # Allow frontend access

# OpenRouteService API client
client = openrouteservice.Client(key="5b3ce3597851110001cf62487728600986d14f3a8c4bce2711134303")

# Load crime dataset
file_path = "crime_dataset_final_cleaned_processed.csv"
df = pd.read_csv(file_path)
df = df[['Latitude', 'Longitude']].dropna()

def geocode(location):
    """Convert location name to latitude/longitude using OpenRouteService."""
    try:
        response = client.pelias_search(text=location)
        if response and response["features"]:
            return response["features"][0]["geometry"]["coordinates"][::-1]  # Convert (lon, lat) to (lat, lon)
    except Exception as e:
        print(f"❌ Geocoding error for {location}: {e}")
    return None

def filter_crimes_along_route(route_coords, buffer_distance=500):
    """Filter crime hotspots within a given buffer distance (meters) along the route."""
    route_line = LineString(route_coords)
    nearby_crimes = []

    for _, row in df.iterrows():
        crime_point = Point(row["Longitude"], row["Latitude"])
        distance = route_line.distance(crime_point) * 111000  # Convert degrees to meters
        if distance <= buffer_distance:
            nearby_crimes.append((row["Latitude"], row["Longitude"]))

    return nearby_crimes

def create_crime_zones(crime_hotspots, buffer_size=0.002):
    """Create high-crime area polygons from filtered crime data."""
    crime_points = [Point(lon, lat) for lat, lon in crime_hotspots]
    if not crime_points:
        return None

    crime_buffers = [p.buffer(buffer_size) for p in crime_points]
    return unary_union(crime_buffers)  # Merge overlapping zones

def is_route_in_crime_zone(route_coords, crime_polygon):
    """Check if a route intersects with a high-crime zone."""
    route_line = LineString(route_coords)
    return route_line.intersects(crime_polygon)

def find_safe_route(source_coords, dest_coords):
    """Find the safest route, avoiding high-crime areas if necessary."""
    try:
        # Get primary route
        primary_route = client.directions(
            coordinates=[source_coords[::-1], dest_coords[::-1]],  # Convert (lat, lon) to (lon, lat)
            profile="driving-car",
            format="geojson"
        )

        # Extract primary route coordinates
        route_coords = [(coord[1], coord[0]) for coord in primary_route['features'][0]['geometry']['coordinates']]

        # Find crime hotspots along the primary route
        crime_hotspots_primary = filter_crimes_along_route(route_coords, buffer_distance=500)

        # Generate crime zones
        crime_zones = create_crime_zones(crime_hotspots_primary)

        alternative_route = None
        crime_hotspots_alt = []

        if crime_zones and is_route_in_crime_zone(route_coords, crime_zones):
            print("⚠ WARNING: Your route passes through a high-crime area!")

            # Get alternative route avoiding crime zones
            alternative_route = client.directions(
                coordinates=[source_coords[::-1], dest_coords[::-1]],
                profile="driving-car",
                format="geojson",
                options={"avoid_polygons": mapping(crime_zones)}
            )

            # Extract alternative route coordinates
            alt_route_coords = [(coord[1], coord[0]) for coord in alternative_route['features'][0]['geometry']['coordinates']]

            # Find crime hotspots along the alternative route
            crime_hotspots_alt = filter_crimes_along_route(alt_route_coords, buffer_distance=500)

        return {
            "primary_route": primary_route,
            "alternative_route": alternative_route,
            "crime_hotspots_primary": crime_hotspots_primary,
            "crime_hotspots_alternative": crime_hotspots_alt
        }

    except Exception as e:
        print(f"❌ Error calculating route: {e}")
        return None

@app.route("/get_safe_route", methods=["POST"])
def get_safe_route():
    """API Endpoint to get the safest route between two locations."""
    data = request.json
    source = data["source"]
    destination = data["destination"]

    # Convert location names to coordinates
    source_coords = geocode(source)
    destination_coords = geocode(destination)

    if not source_coords or not destination_coords:
        return jsonify({"error": "Invalid source or destination"}), 400

    # Get the safe route and crime zones
    safe_route = find_safe_route(source_coords, destination_coords)

    if not safe_route:
        return jsonify({"error": "Route calculation failed"}), 500

    return jsonify(safe_route)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
