import json
import gzip
import io
import requests
from datetime import datetime, timedelta
import pandas as pd
import os

URL = "https://raw.githubusercontent.com/caltech-netlab/acnportal-experiments/master/examples/2-Algorithm-Comparison/2.1-Comparing-Algorithms-with-Constrained-Infrastructure/events/caltech_20190301T000000_20190401T000000_5m_208V_6.6kW.json.gz"
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_OUT = os.path.join(OUTPUT_DIR, "caltech_acn_sessions.json")
CSV_OUT = os.path.join(OUTPUT_DIR, "caltech_acn_sessions.csv")

def main():
    print(f"Downloading ACN-Data snapshot from {URL}...")
    r = requests.get(URL, timeout=30)
    r.raise_for_status()
    print("Downloaded. Decompressing and parsing JSON...")
    
    with gzip.GzipFile(fileobj=io.BytesIO(r.content)) as gz:
        raw_text = gz.read().decode('utf-8')
    
    # Outer JSON decode
    first_pass = json.loads(raw_text)
    data = json.loads(first_pass) if isinstance(first_pass, str) else first_pass
    
    context_dict = data.get("context_dict", {})
    print(f"Parsed {len(context_dict)} context objects.")
    
    # Base simulation start is 2019-03-01 00:00:00 Los Angeles time (PST, UTC-8)
    sim_start = datetime(2019, 3, 1, 0, 0, 0)
    timestep_minutes = 5
    
    # Extract batteries
    batteries = {}
    for obj_id, obj in context_dict.items():
        if "Battery" in obj.get("class", ""):
            attrs = obj.get("attributes", {})
            batteries[obj_id] = {
                "max_power": attrs.get("_max_power", 6.6),
                "capacity": attrs.get("_capacity", 50.0)
            }
            
    # Extract EVs
    sessions = []
    standin_count = 0
    
    for obj_id, obj in context_dict.items():
        if "EV" in obj.get("class", ""):
            attrs = obj.get("attributes", {})
            arrival_step = attrs.get("_arrival", 0)
            dep_step = attrs.get("_departure", 0)
            est_dep_step = attrs.get("_estimated_departure", dep_step)
            req_energy = attrs.get("_requested_energy", 0.0)
            station_id = attrs.get("_station_id", "CA-UNKNOWN")
            session_id = attrs.get("_session_id", f"caltech_{obj_id}")
            batt_id = attrs.get("_battery")
            batt_info = batteries.get(batt_id, {"max_power": 6.6, "capacity": 50.0})
            
            arrival_dt = sim_start + timedelta(minutes=arrival_step * timestep_minutes)
            dep_dt = sim_start + timedelta(minutes=dep_step * timestep_minutes)
            est_dep_dt = sim_start + timedelta(minutes=est_dep_step * timestep_minutes)
            
            # Check if standin was used (if requested departure matches departure and rounded energy)
            is_standin = (dep_step == est_dep_step)
            if is_standin:
                standin_count += 1
                
            sessions.append({
                "session_id": str(session_id),
                "station_id": str(station_id),
                "arrival_step": int(arrival_step),
                "departure_step": int(dep_step),
                "estimated_departure_step": int(est_dep_step),
                "arrival_time": arrival_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "departure_time": dep_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "estimated_departure_time": est_dep_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "date": arrival_dt.strftime("%Y-%m-%d"),
                "requested_energy_kwh": round(float(req_energy), 3),
                "max_power_kw": round(float(batt_info["max_power"]), 2),
                "battery_capacity_kwh": round(float(batt_info["capacity"]), 2),
                "is_standin": is_standin
            })
            
    # Sort chronologically by arrival_step, then departure_step
    sessions.sort(key=lambda x: (x["arrival_step"], x["departure_step"]))
    
    print(f"Total extracted sessions: {len(sessions)}")
    print(f"Sessions using stand-in values: {standin_count} ({round(standin_count/len(sessions)*100, 1)}%)")
    
    # Save clean JSON
    with open(JSON_OUT, "w") as f:
        json.dump(sessions, f, indent=2)
    print(f"Saved JSON to {JSON_OUT}")
    
    # Save clean CSV
    df = pd.DataFrame(sessions)
    df.to_csv(CSV_OUT, index=False)
    print(f"Saved CSV to {CSV_OUT}")
    
    # Summary of dates
    date_counts = df['date'].value_counts().sort_index()
    print("Sample daily counts:")
    print(date_counts.head(10))

if __name__ == "__main__":
    main()
