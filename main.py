import googlemaps
import pandas as pd
import webbrowser
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import urllib.parse

import os
import googlemaps

gmaps = googlemaps.Client(
    key=os.getenv("GOOGLE_MAPS_API_KEY")
)

# 🔧 convertir hora a minutos
def convert_time_to_minutes(time_obj):
    import pandas as pd

    # Si viene como string
    if isinstance(time_obj, str):
        time_obj = pd.to_datetime(time_obj).time()

    # Si viene como Timestamp
    if isinstance(time_obj, pd.Timestamp):
        time_obj = time_obj.time()

    # Si es NaN
    if pd.isna(time_obj):
        return 0

    return time_obj.hour * 60 + time_obj.minute

# 📊 cargar Excel
def load_data(file_name):
    df = pd.read_excel(file_name)
    df.columns = df.columns.str.strip().str.lower()
    df = df.dropna(subset=["direccion"])
    return df

# 🚀 matriz
def get_distance_matrix(addresses):
    try:
        matrix = gmaps.distance_matrix(
        addresses,
        addresses,
        mode="driving"
    )

    except Exception as e:
        print("ERROR GOOGLE:", e)
        raise e
    distances = []
    for row in matrix['rows']:
        row_distances = []
        for elem in row['elements']:
            if elem['status'] == 'OK':
                row_distances.append(elem['distance']['value'])
            else:
                row_distances.append(999999)
        distances.append(row_distances)

    return distances

# 🚀 optimización con tiempo
def optimize_routes(distance_matrix, time_windows, num_vehicles=2):
    from ortools.constraint_solver import routing_enums_pb2
    from ortools.constraint_solver import pywrapcp

    manager = pywrapcp.RoutingIndexManager(len(distance_matrix), num_vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)

    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return max(1, distance_matrix[from_node][to_node] // 60)

    transit_callback_index = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    routing.AddDimension(
        transit_callback_index,
        30,
        1440,
        False,
        "Time"
    )

    time_dimension = routing.GetDimensionOrDie("Time")

    for i, (start, end) in enumerate(time_windows):
        index = manager.NodeToIndex(i)
        time_dimension.CumulVar(index).SetRange(start, end)

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC

    solution = routing.SolveWithParameters(search_parameters)

    routes = []
    if solution:
        for vehicle_id in range(num_vehicles):
            index = routing.Start(vehicle_id)
            route = []

            while not routing.IsEnd(index):
                route.append(manager.IndexToNode(index))
                index = solution.Value(routing.NextVar(index))

            route.append(manager.IndexToNode(index))
            routes.append(route)

    return routes

# 🌍 link maps
def generate_google_maps_link(route, locations):
    import urllib.parse

    ordered = [locations[i] for i in route]

    origin = urllib.parse.quote(ordered[0])
    destination = urllib.parse.quote(ordered[-1])

    waypoints = "|".join(
        urllib.parse.quote(loc) for loc in ordered[1:-1]
    )

    url = f"https://www.google.com/maps/dir/?api=1&origin={origin}&destination={destination}&waypoints={waypoints}&travelmode=driving"

    return url

# 🚀 MAIN (ÚNICO)
if __name__ == "__main__":
    print("📥 Cargando Excel")
    df = load_data("clientes.xlsx")

    df["dia"] = df["dia"].str.strip().str.lower()
    df = df.dropna(subset=["direccion", "dia"])

    df["direccion"] = df["direccion"].astype(str).str.strip()

    df = df[
    (df["direccion"] != "") &
    (df["direccion"] != "nan") &
    (df["direccion"].str.len() > 10) &
    (df["direccion"].str.contains("NSW|VIC|QLD", case=False))
]
     
    print("Días detectados:", df["dia"].unique())

    dias = df["dia"].unique()

    for dia in dias:
        print(f"\n📅 Ruta para: {dia}")

        df_dia = df[df["dia"] == dia]

        locations = df_dia["direccion"].tolist()

        time_windows = []
        for i in range(len(df_dia)):
            start = convert_time_to_minutes(df_dia.iloc[i]["hora inicio"])
            end = convert_time_to_minutes(df_dia.iloc[i]["hora fin"])
            time_windows.append((start, end))

        warehouse = "51 Nelson Rd, Yennora NSW 2161, Australia"
        locations = [warehouse] + locations
        time_windows.insert(0, (0, 1440))

        print("Calculando matriz")
        distance_matrix = get_distance_matrix(locations)

        print("Optimizando ruta")
        route = optimize_routes(distance_matrix, time_windows)

        print("🚚 Ruta:")
        for i in route:
            print(f"{locations[i]}")

        link = generate_google_maps_link(route, locations)

        print("\n🌍 Google Maps:")
        print(link)

        webbrowser.open(link)

        print("\n✅ CLIENTES LIMPIOS:")
        print(df[["cliente", "direccion"]])

        print("\n📍 LOCATIONS ORIGINALES:")
        for loc in locations:
            print(loc)

        print("\n🧭 ROUTE ÍNDICES:")
        print(route)

        print("\n📍 LOCATIONS ORDENADAS (ANTES DEL LINK):")
        ordered = [locations[i] for i in route]
        for loc in ordered:
            print(loc)
    
