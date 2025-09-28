from pydantic import BaseModel, Field, validator
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
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

    @validator('timestamp', 'created_at', pre=True)
    def validate_timestamp(cls, v):
        if v is None:
            return v
        if isinstance(v, datetime):
            return v.isoformat() + 'Z'
        return v


class TemperatureReading(BaseModel):
    """Temperature-specific sensor reading"""
    id: Optional[int] = None
    sensor_id: str
    timestamp: str
    location_lat: float = Field(..., ge=-90, le=90)
    location_lng: float = Field(..., ge=-180, le=180)
    temperature_celsius: float = Field(..., ge=-50, le=70, description="Temperature in Celsius")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    created_at: Optional[str] = None


class HumidityReading(BaseModel):
    """Humidity-specific sensor reading"""
    id: Optional[int] = None
    sensor_id: str
    timestamp: str
    location_lat: float = Field(..., ge=-90, le=90)
    location_lng: float = Field(..., ge=-180, le=180)
    humidity_percentage: float = Field(..., ge=0, le=100, description="Relative humidity percentage")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    created_at: Optional[str] = None


class LightReading(BaseModel):
    """Light-specific sensor reading"""
    id: Optional[int] = None
    sensor_id: str
    timestamp: str
    location_lat: float = Field(..., ge=-90, le=90)
    location_lng: float = Field(..., ge=-180, le=180)
    light_lux: float = Field(..., ge=0, description="Light intensity in lux")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    created_at: Optional[str] = None


class SensorStatus(BaseModel):
    """Status information for a sensor type"""
    total_readings: int = Field(..., description="Total number of readings")
    sensor_count: int = Field(..., description="Number of active sensors")
    latest_reading: Optional[str] = Field(None, description="Timestamp of latest reading")
    earliest_reading: Optional[str] = Field(None, description="Timestamp of earliest reading")
    avg_value: float = Field(..., description="Average sensor value")
    max_value: float = Field(..., description="Maximum sensor value")
    min_value: float = Field(..., description="Minimum sensor value")
    status: str = Field(..., description="Sensor status (active/inactive)")


class SystemStatus(BaseModel):
    """Overall system status"""
    timestamp: str = Field(..., description="Status timestamp")
    sensors: Dict[str, SensorStatus] = Field(..., description="Status per sensor type")
    total_readings: int = Field(..., description="Total readings across all sensors")
    active_sensors: int = Field(..., description="Total number of active sensors")
    data_quality: str = Field(..., description="Overall data quality assessment")


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


class SensorsStatusResponse(ApiResponse):
    """Response model for sensors status endpoint"""
    status: SystemStatus = Field(..., description="System status information")


class ErrorResponse(BaseModel):
    """Error response model"""
    success: bool = Field(False, description="Request success status")
    error: str = Field(..., description="Error message")
    timestamp: str = Field(..., description="Error timestamp")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


class QueryFilters(BaseModel):
    """Query filters for data retrieval"""
    limit: int = Field(100, ge=1, le=1000, description="Maximum records to return")
    hours: int = Field(24, ge=1, le=168, description="Hours of historical data")
    sensor_type: Optional[SensorType] = Field(None, description="Filter by sensor type")
    sensor_id: Optional[str] = Field(None, description="Filter by specific sensor")
    start_time: Optional[datetime] = Field(None, description="Start time for data range")
    end_time: Optional[datetime] = Field(None, description="End time for data range")
