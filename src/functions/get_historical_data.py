from fastapi import FastAPI, HTTPException, Query, Path, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from mangum import Mangum
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import json

from src.database.db_manager import DatabaseManager
from src.models.sensor_models import (
    SensorDataResponse,
    ApiResponse,
    SensorType
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TEMPERATURE_TABLE = os.environ.get('TEMPERATURE_TABLE', 'iot_temperature_data_dev')
HUMIDITY_TABLE = os.environ.get('HUMIDITY_TABLE', 'iot_humidity_data_dev')
LIGHT_TABLE = os.environ.get('LIGHT_TABLE', 'iot_light_data_dev')
ALL_SENSORS_TABLE = os.environ.get('ALL_SENSORS_TABLE', 'iot_all_sensors_data_dev')

db_manager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global db_manager
    db_manager = DatabaseManager()
    logger.info("FastAPI IoT Service started")
    yield
    if db_manager:
        db_manager.close_connection()
    logger.info("FastAPI IoT Service shutdown")


app = FastAPI(
    title="IoT Historical Data API",
    description="REST API for retrieving IoT sensor historical data",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


def get_db_manager() -> DatabaseManager:
    """Dependency to get database manager"""
    global db_manager
    if db_manager is None:
        db_manager = DatabaseManager()
    return db_manager


class HistoricalDataService:
    """Service for retrieving historical sensor data"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    async def get_all_sensors_data(self, limit: int = 100, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent data from all sensors"""
        try:
            since_time = (datetime.utcnow() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')

            query = f"""
                SELECT sensor_id, sensor_type, timestamp, location_lat, location_lng, 
                       sensor_value, unit, metadata, created_at
                FROM {ALL_SENSORS_TABLE}
                WHERE timestamp >= %s
                ORDER BY timestamp DESC
                LIMIT %s
                """

            results = self.db_manager.execute_query(query, (since_time, limit), fetch_results=True)
            return self.format_sensor_results(results)

        except Exception as e:
            logger.error(f"Error retrieving all sensors data: {e}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    async def get_sensor_type_data(self, sensor_type: str, limit: int = 100, hours: int = 24) -> List[Dict[str, Any]]:
        """Get data for specific sensor type"""
        try:
            since_time = (datetime.utcnow() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')

            table_map = {
                'temperature': TEMPERATURE_TABLE,
                'humidity': HUMIDITY_TABLE,
                'light': LIGHT_TABLE
            }

            if sensor_type not in table_map:
                raise HTTPException(status_code=400, detail=f"Unknown sensor type: {sensor_type}")

            table_name = table_map[sensor_type]

            if sensor_type == 'temperature':
                value_column = 'temperature_celsius'
                unit = '°C'
            elif sensor_type == 'humidity':
                value_column = 'humidity_percentage'
                unit = '%'
            elif sensor_type == 'light':
                value_column = 'light_lux'
                unit = 'lux'

            query = f"""
                SELECT sensor_id, timestamp, location_lat, location_lng, 
                       {value_column} as sensor_value, metadata, created_at
                FROM {table_name}
                WHERE timestamp >= %s
                ORDER BY timestamp DESC
                LIMIT %s
                """

            results = self.db_manager.execute_query(query, (since_time, limit), fetch_results=True)

            # Add sensor type and unit to results
            formatted_results = []
            for row in results:
                row['sensor_type'] = sensor_type
                row['unit'] = unit
                formatted_results.append(row)

            return self.format_sensor_results(formatted_results)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving {sensor_type} data: {e}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    async def get_sensors_status(self) -> Dict[str, Any]:
        """Get status information about all sensors"""
        try:
            status_query = f"""
                SELECT 
                    sensor_type,
                    COUNT(*) as total_readings,
                    COUNT(DISTINCT sensor_id) as sensor_count,
                    MAX(timestamp) as latest_reading,
                    MIN(timestamp) as earliest_reading,
                    AVG(sensor_value) as avg_value,
                    MAX(sensor_value) as max_value,
                    MIN(sensor_value) as min_value
                FROM {ALL_SENSORS_TABLE}
                WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                GROUP BY sensor_type
                """

            results = self.db_manager.execute_query(status_query, fetch_results=True)

            status_info = {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'sensors': {},
                'total_readings': 0,
                'active_sensors': 0,
                'data_quality': 'good'
            }

            for row in results:
                sensor_type = row['sensor_type']
                status_info['sensors'][sensor_type] = {
                    'total_readings': int(row['total_readings']),
                    'sensor_count': int(row['sensor_count']),
                    'latest_reading': row['latest_reading'].isoformat() + 'Z' if row['latest_reading'] else None,
                    'earliest_reading': row['earliest_reading'].isoformat() + 'Z' if row['earliest_reading'] else None,
                    'avg_value': float(row['avg_value']) if row['avg_value'] else 0,
                    'max_value': float(row['max_value']) if row['max_value'] else 0,
                    'min_value': float(row['min_value']) if row['min_value'] else 0,
                    'status': 'active' if row['latest_reading'] and
                                          (datetime.utcnow() - row[
                                              'latest_reading']).total_seconds() < 300 else 'inactive'
                }
                status_info['total_readings'] += int(row['total_readings'])
                status_info['active_sensors'] += int(row['sensor_count'])

            return status_info

        except Exception as e:
            logger.error(f"Error retrieving sensors status: {e}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    async def get_sensor_statistics(self, sensor_type: str, hours: int = 24) -> Dict[str, Any]:
        """Get statistical data for a sensor type"""
        try:
            since_time = (datetime.utcnow() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')

            query = f"""
                SELECT 
                    COUNT(*) as reading_count,
                    AVG(sensor_value) as avg_value,
                    MAX(sensor_value) as max_value,
                    MIN(sensor_value) as min_value,
                    STDDEV(sensor_value) as std_deviation,
                    MAX(timestamp) as latest_reading,
                    MIN(timestamp) as earliest_reading
                FROM {ALL_SENSORS_TABLE}
                WHERE sensor_type = %s AND timestamp >= %s
                """

            results = self.db_manager.execute_query(query, (sensor_type, since_time), fetch_results=True)

            if not results:
                return {
                    'sensor_type': sensor_type,
                    'period_hours': hours,
                    'reading_count': 0,
                    'statistics': None
                }

            row = results[0]
            return {
                'sensor_type': sensor_type,
                'period_hours': hours,
                'reading_count': int(row['reading_count']),
                'statistics': {
                    'avg_value': float(row['avg_value']) if row['avg_value'] else 0,
                    'max_value': float(row['max_value']) if row['max_value'] else 0,
                    'min_value': float(row['min_value']) if row['min_value'] else 0,
                    'std_deviation': float(row['std_deviation']) if row['std_deviation'] else 0,
                    'latest_reading': row['latest_reading'].isoformat() + 'Z' if row['latest_reading'] else None,
                    'earliest_reading': row['earliest_reading'].isoformat() + 'Z' if row['earliest_reading'] else None
                }
            }

        except Exception as e:
            logger.error(f"Error retrieving sensor statistics: {e}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    def format_sensor_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format database results for API response"""
        formatted_results = []

        for row in results:
            formatted_row = {}

            for key, value in row.items():
                if key in ['timestamp', 'created_at'] and value:
                    formatted_row[key] = value.isoformat() + 'Z'
                elif key == 'metadata' and value:
                    try:
                        formatted_row[key] = json.loads(value) if isinstance(value, str) else value
                    except:
                        formatted_row[key] = {}
                elif isinstance(value, (int, float)):
                    formatted_row[key] = float(value)
                else:
                    formatted_row[key] = value

            formatted_results.append(formatted_row)

        return formatted_results


# Root endpoint handler
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "IoT Historical Data API",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "endpoints": {
            "health": "/health",
            "all_sensors": "/api/v1/sensors/historical",
            "sensor_type": "/api/v1/sensors/{sensor_type}/historical",
            "statistics": "/api/v1/sensors/{sensor_type}/statistics",
            "status": "/api/v1/sensors/status",
            "latest": "/api/v1/sensors/latest"
        }
    }


@app.get("/health")
async def health_check(db: DatabaseManager = Depends(get_db_manager)):
    """Health check endpoint"""
    try:
        # Simple database connectivity check
        db.execute_query("SELECT 1", fetch_results=True)
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "database": "connected"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


@app.get("/api/v1/sensors/historical", response_model=SensorDataResponse)
async def get_all_sensors_historical_data(
        limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
        hours: int = Query(24, ge=1, le=168, description="Hours of historical data to retrieve"),
        db: DatabaseManager = Depends(get_db_manager)
):
    """Get historical data from all sensors"""
    try:
        service = HistoricalDataService(db)
        data = await service.get_all_sensors_data(limit=limit, hours=hours)

        return SensorDataResponse(
            success=True,
            data=data,
            count=len(data),
            filters={"limit": limit, "hours": hours},
            timestamp=datetime.utcnow().isoformat() + "Z"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_all_sensors_historical_data: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/v1/sensors/{sensor_type}/historical", response_model=SensorDataResponse)
async def get_sensor_type_historical_data(
        sensor_type: SensorType = Path(..., description="Type of sensor"),
        limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
        hours: int = Query(24, ge=1, le=168, description="Hours of historical data to retrieve"),
        db: DatabaseManager = Depends(get_db_manager)
):
    """Get historical data for specific sensor type"""
    try:
        service = HistoricalDataService(db)
        data = await service.get_sensor_type_data(sensor_type.value, limit=limit, hours=hours)

        return SensorDataResponse(
            success=True,
            sensor_type=sensor_type.value,
            data=data,
            count=len(data),
            filters={"limit": limit, "hours": hours},
            timestamp=datetime.utcnow().isoformat() + "Z"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_sensor_type_historical_data: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/v1/sensors/status")
async def get_sensors_status(db: DatabaseManager = Depends(get_db_manager)):
    """Get status information about all sensors"""
    try:
        service = HistoricalDataService(db)
        status = await service.get_sensors_status()

        return ApiResponse(
            success=True,
            data=status,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_sensors_status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/v1/sensors/{sensor_type}/statistics")
async def get_sensor_statistics(
        sensor_type: SensorType = Path(..., description="Type of sensor"),
        hours: int = Query(24, ge=1, le=168, description="Hours for statistical analysis"),
        db: DatabaseManager = Depends(get_db_manager)
):
    """Get statistical information for a sensor type"""
    try:
        service = HistoricalDataService(db)
        statistics = await service.get_sensor_statistics(sensor_type.value, hours=hours)

        return ApiResponse(
            success=True,
            data=statistics,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_sensor_statistics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/v1/sensors/latest")
async def get_latest_readings(
        sensor_type: Optional[SensorType] = Query(None, description="Filter by sensor type"),
        db: DatabaseManager = Depends(get_db_manager)
):
    """Get the latest readings from sensors"""
    try:
        service = HistoricalDataService(db)

        if sensor_type:
            data = await service.get_sensor_type_data(sensor_type.value, limit=1, hours=1)
        else:
            data = await service.get_all_sensors_data(limit=10, hours=1)

        return ApiResponse(
            success=True,
            data=data,
            count=len(data),
            timestamp=datetime.utcnow().isoformat() + "Z"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_latest_readings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    )


handler = Mangum(app, lifespan="off")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        reload=os.environ.get("ENVIRONMENT") != "PROD",
        log_level="info"
    )