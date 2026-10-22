from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import uuid

# Vehicle Variety Templates
VEHICLE_PRESETS = {
    "EV Car": {
        "default_battery": 50.0,
        "default_max_power": 7.2,
        "icon": "car",
        "description": "Standard Workplace Electric Car (e.g. Model 3, Leaf, Bolt)"
    },
    "EV Bike": {
        "default_battery": 3.0,
        "default_max_power": 1.0,
        "icon": "bike",
        "description": "Lightweight Electric Motorcycle or Commuter Bike"
    },
    "EV Scooter": {
        "default_battery": 2.5,
        "default_max_power": 0.8,
        "icon": "zap",
        "description": "Electric Scooter (e.g. Ather, Ola, Segway)"
    },
    "EV SUV / Van": {
        "default_battery": 75.0,
        "default_max_power": 11.0,
        "icon": "truck",
        "description": "Fleet Van or High-Capacity Long-Range EV"
    }
}

@dataclass
class Vehicle:
    id: str
    user_id: str
    user_name: str
    name: str
    vehicle_type: str  # "EV Car", "EV Bike", "EV Scooter", "EV SUV / Van"
    battery_capacity_kwh: float
    max_rate_kw: float
    current_charge_pct: float = 20.0
    target_charge_pct: float = 100.0
    is_plugged_in: bool = False
    current_session_id: Optional[str] = None
    priority_tier: str = "standard"  # "urgent", "standard", "flexible"
    departure_time: str = "17:00"
    priority_fleet_rank: int = 1  # 1 = primary, 2 = secondary, etc.

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "name": self.name,
            "vehicle_type": self.vehicle_type,
            "battery_capacity_kwh": self.battery_capacity_kwh,
            "max_rate_kw": self.max_rate_kw,
            "current_charge_pct": round(self.current_charge_pct, 1),
            "target_charge_pct": round(self.target_charge_pct, 1),
            "is_plugged_in": self.is_plugged_in,
            "current_session_id": self.current_session_id,
            "priority_tier": self.priority_tier,
            "departure_time": self.departure_time,
            "priority_fleet_rank": self.priority_fleet_rank
        }

@dataclass
class User:
    id: str
    username: str
    password_hash: str
    full_name: str
    role: str = "user"  # "admin" or "user"
    vehicles: List[Vehicle] = field(default_factory=list)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "full_name": self.full_name,
            "role": self.role,
            "vehicles": [v.to_dict() for v in self.vehicles]
        }

@dataclass
class SessionDecisionExplanation:
    vehicle_facts: Dict
    calculated_values: Dict
    priority_breakdown: Dict
    allocation_phases: Dict
    final_sentence: str
    one_line_reason: str

    def to_dict(self):
        return {
            "vehicle_facts": self.vehicle_facts,
            "calculated_values": self.calculated_values,
            "priority_breakdown": self.priority_breakdown,
            "allocation_phases": self.allocation_phases,
            "final_sentence": self.final_sentence,
            "one_line_reason": self.one_line_reason
        }
