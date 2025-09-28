from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from enum import Enum


class SensorType(str, Enum):
    """Supported sensor types"""
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    LIGHT = "light"


class Location(BaseModel):
    """Geographic location model"""
    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lng: float = Field(..., ge=-180, le=180, description="Longitude")


class SensorMetadata(BaseModel):
    """Sensor metadata model"""
    interval_seconds: Optional[int] = Field(None, description="Sensor reading interval")
    sensor_version: Optional[str] = Field(None, description="Sensor firmware version")
    battery_level: Optional[float] = Field(None, ge=0, le=100, description="Battery level percentage")
    signal_strength: Optional[float] = Field(None, description="Signal strength in dBm")
    calibration_date: Optional[str] = Field(None, description="Last calibration date")
    sensitivity: Optional[str] = Field(None, description="Sensor sensitivity level")


class SensorReading(BaseModel):
    """Individual sensor reading model"""
    id: Optional[int] = Field(None, description="Database record ID")
    sensor_id: str = Field(..., description="Unique sensor identifier")
    sensor_type: Optional[SensorType] = Field(None, description="Type of sensor")
    timestamp: str = Field(..., description="Reading timestamp in ISO format")
    location_lat: float = Field(..., ge=-90, le=90, description="Sensor latitude")
    location_lng: float = Field(..., ge=-180, le=180, description="Sensor longitude")
    sensor_value: float = Field(..., description="Sensor reading value")
    unit: str = Field(..., description="Unit of measurement")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    created_at: Optional[str] = Field(None, description="Record creation timestamp")


class ApiResponse(BaseModel):
    """Generic API response model"""
    success: bool = Field(..., description="Request success status")
    data: Optional[Any] = Field(None, description="Response data")
    count: Optional[int] = Field(None, description="Number of records returned")
    timestamp: str = Field(..., description="Response timestamp")
    message: Optional[str] = Field(None, description="Additional message")


class SensorDataResponse(ApiResponse):
    """Response model for sensor data endpoints"""
    sensor_type: Optional[str] = Field(None, description="Sensor type filter applied")
    filters: Optional[Dict[str, Any]] = Field(None, description="Applied filters")
    data: List[SensorReading] = Field(..., description="Sensor readings")



