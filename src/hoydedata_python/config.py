from pydantic_settings import BaseSettings, SettingsConfigDict


class HoydeDataConfig(BaseSettings):
    """
    Configuration for HoydeData.
    """

    API_URL: str = "https://hoydedata.no/arcgis/rest/services"
    API_LAYER: str = "NHM_DTM_25833"

    LOG_LEVEL: str = "INFO"

    ELEVATION_SERVICE_MAX_SIZE: int = 2000  # Maximum pixel dimension supported by elevation service
    DEFAULT_CRS: int = 25833  # UTM zone 33N epsg:25833
    URL_METADATA: str = "http://hoydedata.no/laserservices/rest/projectMetadata.ashx"
    URL_EXPORT: str = "https://hoydedata.no/laserservices/rest/startExport.ashx"
    URL_STATUS: str = "https://hoydedata.no/laserservices/rest/exportStatus.ashx"

    API_TIMEOUT: int = 500
    API_RETRY_ATTEMPTS: int = 3
    API_RETRY_MIN_WAIT: int = 1  # seconds
    API_RETRY_MAX_WAIT: int = 10  # seconds
    API_MAX_CONCURRENCY: int = 50

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="HØYDEDATA_",
        env_file_encoding="utf-8",
        extra="allow",
    )


settings = HoydeDataConfig()
