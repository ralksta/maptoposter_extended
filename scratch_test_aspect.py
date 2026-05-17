import osmnx as ox
import geopandas as gpd

gdf_country = ox.geocode_to_gdf("Japan")
minx, miny, maxx, maxy = gdf_country.total_bounds
data_w = maxx - minx
data_h = maxy - miny
aspect = data_h / data_w if data_w > 0 else 1.0

print(f"Bounds: {minx:.2f}, {miny:.2f}, {maxx:.2f}, {maxy:.2f}")
print(f"Data width: {data_w:.2f}")
print(f"Data height: {data_h:.2f}")
print(f"Aspect: {aspect:.2f}")

