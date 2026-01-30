import numpy as np
from noise import snoise2
import json

def generate_disaster_map(size=100, scale=20.0):
    # 75% City (Flat/Grid-like noise), 25% Jungle (Rugged noise)
    map_data = []
    for y in range(size):
        row = []
        for x in range(size):
            # Generate base terrain using Perlin Noise
            elevation = snoise2(x/scale, y/scale, octaves=6)
            
            # Determine if Jungle (25% of the map) or City (75%)
            # We can bias the noise higher in the "Jungle" sector
            if x > (size * 0.75):
                elevation += 0.3  # Higher, more rugged
            
            # Normalize to 0-1 range
            val = (elevation + 1) / 2
            row.append(round(val, 2))
        map_data.append(row)
    
    return map_data

# Save for the web frontend
with open('map_data.json', 'w') as f:
    json.dump(generate_disaster_map(), f)